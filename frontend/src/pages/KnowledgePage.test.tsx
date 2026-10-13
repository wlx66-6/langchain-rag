import { fireEvent, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import KnowledgePage from './KnowledgePage'
import { knowledgeApi } from '../lib/api'
import { useAuth } from '../lib/auth'
import { apiError } from '../test/fixtures'
import { renderWithProviders } from '../test/render'

vi.mock('../lib/api', () => ({
  knowledgeApi: {
    listDocuments: vi.fn(),
    uploadDocument: vi.fn(),
    deleteDocument: vi.fn(),
  },
}))
vi.mock('../lib/auth', () => ({ useAuth: vi.fn() }))

const mockedApi = vi.mocked(knowledgeApi)
const mockedUseAuth = vi.mocked(useAuth)

const DOC = {
  id: 1,
  filename: '商品说明.txt',
  file_type: 'txt',
  status: 'ready',
  chunk_count: 3,
  created_at: '2026-01-01T00:00:00',
}

function asAdmin() {
  mockedUseAuth.mockReturnValue({
    user: { id: 1, username: 'boss', is_admin: true },
    isAdmin: true,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
  })
}

function pickFile(name = '说明.txt') {
  const input = screen.getByLabelText('选择要上传的文档') as HTMLInputElement
  const file = new File(['内容'], name, { type: 'text/plain' })
  fireEvent.change(input, { target: { files: [file] } })
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedApi.listDocuments.mockResolvedValue([])
})

describe('KnowledgePage 权限', () => {
  it('非管理员看到无权限提示', async () => {
    mockedUseAuth.mockReturnValue({
      user: { id: 2, username: 'alice', is_admin: false },
      isAdmin: false,
      loading: false,
      login: vi.fn(),
      logout: vi.fn(),
    })
    renderWithProviders(<KnowledgePage />)

    expect(await screen.findByText('无权限访问')).toBeTruthy()
    expect(mockedApi.listDocuments).not.toHaveBeenCalled()
  })
})

describe('KnowledgePage 列表', () => {
  beforeEach(asAdmin)

  it('渲染文档列表', async () => {
    mockedApi.listDocuments.mockResolvedValue([DOC])
    renderWithProviders(<KnowledgePage />)

    expect(await screen.findByText('商品说明.txt')).toBeTruthy()
    expect(screen.getByText('已入库')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
  })

  it('空列表展示占位行', async () => {
    renderWithProviders(<KnowledgePage />)
    expect(await screen.findByText('暂无文档，请先上传')).toBeTruthy()
  })

  it('列表加载失败时用 toast 提示', async () => {
    mockedApi.listDocuments.mockRejectedValue(apiError('加载失败'))
    renderWithProviders(<KnowledgePage />)
    expect(await screen.findByText('加载失败')).toBeTruthy()
  })
})

describe('KnowledgePage 上传', () => {
  beforeEach(asAdmin)

  it('上传成功后提示并刷新列表', async () => {
    mockedApi.uploadDocument.mockResolvedValue(DOC)
    renderWithProviders(<KnowledgePage />)
    await screen.findByText('暂无文档，请先上传')

    pickFile()

    expect(await screen.findByText('「说明.txt」上传成功，已入库')).toBeTruthy()
    expect(mockedApi.uploadDocument).toHaveBeenCalled()
    await waitFor(() => expect(mockedApi.listDocuments).toHaveBeenCalledTimes(2))
  })

  it('上传失败时展示后端返回的原因', async () => {
    mockedApi.uploadDocument.mockRejectedValue(apiError('不支持的文件格式：.exe'))
    renderWithProviders(<KnowledgePage />)
    await screen.findByText('暂无文档，请先上传')

    pickFile('virus.exe')

    expect(await screen.findByText('不支持的文件格式：.exe')).toBeTruthy()
  })
})

describe('KnowledgePage 删除', () => {
  beforeEach(asAdmin)

  it('确认后调用删除接口', async () => {
    mockedApi.listDocuments.mockResolvedValue([DOC])
    mockedApi.deleteDocument.mockResolvedValue({})
    renderWithProviders(<KnowledgePage />)
    await screen.findByText('商品说明.txt')

    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    fireEvent.click(await screen.findByRole('button', { name: '确定' }))

    await waitFor(() => expect(mockedApi.deleteDocument).toHaveBeenCalledWith(1))
    expect(await screen.findByText('文档已删除')).toBeTruthy()
  })

  it('取消时不调用删除接口', async () => {
    mockedApi.listDocuments.mockResolvedValue([DOC])
    renderWithProviders(<KnowledgePage />)
    await screen.findByText('商品说明.txt')

    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    fireEvent.click(await screen.findByRole('button', { name: '取消' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(mockedApi.deleteDocument).not.toHaveBeenCalled()
  })

  it('删除失败时展示错误提示', async () => {
    mockedApi.listDocuments.mockResolvedValue([DOC])
    mockedApi.deleteDocument.mockRejectedValue(apiError('文档不存在'))
    renderWithProviders(<KnowledgePage />)
    await screen.findByText('商品说明.txt')

    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    fireEvent.click(await screen.findByRole('button', { name: '确定' }))

    expect(await screen.findByText('文档不存在')).toBeTruthy()
  })
})