/** 前后端共享的数据结构定义，集中在一处，避免各页面各写一份。 */

export interface UserInfo {
  id: number
  username: string
  is_admin: boolean
}

/** 回答里的一条引用资料 */
export interface Citation {
  source: string
  content: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
}

/** 后端返回的原始消息：citations 是 JSON 字符串，需要前端解析成 Citation[] */
export interface ApiMessage {
  id: number
  role: string
  content: string
  citations: string | null
  created_at: string
}

export interface Conversation {
  id: number
  title: string
  updated_at: string
}

export interface KnowledgeDocument {
  id: number
  filename: string
  file_type: string
  status: string
  chunk_count: number
  created_at: string
}

/** 登录 / 刷新令牌接口的返回体 */
export interface AuthTokens {
  access_token: string
  refresh_token: string
}