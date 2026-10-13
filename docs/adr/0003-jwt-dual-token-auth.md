# ADR-0003：JWT 双令牌（access + refresh）鉴权

- **状态**：已接受
- **日期**：2026-10（改造时补记）

## 背景

前端是 SPA，需要「登录一次、长时间不用重登」，同时密码与密钥不能以任何形式泄露或写死。
需要在「无状态鉴权」与「可撤销/可续期」之间取一个折中。

## 决策

采用 **JWT 双令牌**方案：

- **access token**：有效期 `30 分钟`（`settings.access_token_expire_minutes`），
  随每次业务请求放在 `Authorization: Bearer <token>` 头里。
- **refresh token**：有效期 `7 天`（`settings.refresh_token_expire_days`），
  仅用于换取新的 access token。
- 令牌内用 `type` 声明区分 `access` / `refresh`，后端校验时**严格比对类型**，
  防止用 refresh token 直接访问业务接口（见 `app/core/deps.py`）。
- OpenAPI 里的鉴权方案声明为 **HTTP Bearer**（`HTTPBearer`），而**不用** FastAPI 更常见的
  `OAuth2PasswordBearer`：后者会在 `/docs` 声明一条「OAuth2 密码流」，诱导 Swagger 的
  Authorize 按钮以 **`x-www-form-urlencoded` 表单**去调 `tokenUrl`，而本项目登录接口收的是
  **JSON body**，两者对不上，Authorize 按钮必然返回 422——文档里给的调试入口等于是坏的。
  `HTTPBearer` 对应「粘贴一个 access_token」，与实际鉴权方式一致。
- 缺少凭据时统一返回 **401**（而非 `HTTPBearer` 默认的 403），并带 `WWW-Authenticate: Bearer`。
- 密码用 **bcrypt** 存储；由于 bcrypt 只处理 72 字节以内输入，而中文密码每字 3 字节，
  故先做一次 **SHA256 摘要再交给 bcrypt**（`app/core/security.py` 的 `_prehash`）。
- `jwt_secret` **不设默认值**：缺失时启动直接报错并提示生成方式
  （`python -c "import secrets; print(secrets.token_urlsafe(48))"`），杜绝「用了弱默认密钥还以为没事」。
- CORS 允许来源从配置读取（默认 `http://127.0.0.1:5173`），**不使用 `*` 通配**。

## 理由

1. **双令牌是「体验」与「安全」的平衡**：access 短命，即使泄露影响窗口也小；
   refresh 长命但只走 `/api/auth/refresh` 一个入口，便于集中校验。
2. **前端不碰密钥**：密钥与签名只存在于后端 `.env`，前端只持有令牌字符串，
   即便前端代码被查看也没有秘密可泄露。
3. **SHA256 预哈希是被 bcrypt 限制逼出来的必要手段**，不是「加盐做样子」——
   它解决的是「超过 72 字节的密码会被静默截断」这一真实缺陷。

## 后果

- 优点：无状态、可水平扩展、前端体验好、无明文秘密。
- 代价与已知限制：
  - **本项目未实现 refresh token 的服务端吊销列表（黑名单）**，因此「登出」是前端丢弃令牌，
    服务端无法主动使某个 refresh token 立即失效。若要做，需要引入令牌存储或 `jti` + 黑名单。
  - 令牌存放于前端 `localStorage`，对 XSS 的抵抗依赖前端不引入不可信脚本。
- 相关：ADR-0001（架构）、`app/core/security.py`、`app/core/deps.py`、`app/routers/auth.py`。