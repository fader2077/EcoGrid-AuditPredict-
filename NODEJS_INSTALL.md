# Node.js 安裝指南

## 方法 1: 使用 winget（Windows 10/11）

```powershell
winget install OpenJS.NodeJS.LTS
```

安裝完成後，重新啟動 PowerShell 終端。

## 方法 2: 手動下載安裝

1. 訪問 Node.js 官網: https://nodejs.org/
2. 下載 LTS 版本（推薦 v20.x）
3. 執行安裝程序
4. 確認安裝成功:
   ```powershell
   node --version
   npm --version
   ```

## 方法 3: 使用 Chocolatey

```powershell
# 如果已安裝 Chocolatey
choco install nodejs-lts
```

## 安裝後驗證

```powershell
# 檢查 Node.js 版本
node --version

# 檢查 npm 版本
npm --version

# 應該看到類似輸出:
# v20.11.0
# 10.4.0
```

## 安裝 Frontend 依賴

```powershell
cd frontend
npm install
```

## 啟動 Frontend 開發伺服器

```powershell
cd frontend
npm run dev
```

Frontend 將運行於: **http://localhost:5173**

## 常見問題

### 問題: npm 不是內部或外部命令

**解決方案**: 
1. 確認 Node.js 已正確安裝
2. 重新啟動 PowerShell 終端
3. 檢查環境變數是否包含 Node.js 路徑（通常在 `C:\Program Files\nodejs\`）

### 問題: npm install 失敗

**解決方案**:
```powershell
# 清除快取
npm cache clean --force

# 刪除 node_modules
Remove-Item -Recurse -Force node_modules

# 重新安裝
npm install
```

### 問題: 端口 5173 被佔用

**解決方案**:
```powershell
# 在 vite.config.js 中修改端口
# server: { port: 3000 }
```
