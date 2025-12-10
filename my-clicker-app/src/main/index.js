import { app, shell, BrowserWindow, ipcMain, screen } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
const { spawn } = require('child_process')

let pyProc = null

// --- 1. 启动 Python 后端 ---
const createPyProc = () => {
  let script = null
  let cmd = null
  let args = []

  if (is.dev) {
    // 开发环境：假设 server.py 在项目根目录
    script = join(__dirname, '../../server.py')
    cmd = 'python'
    args = [script]
    console.log('Starting Python backend (Dev):', script)
  } else {
    // 生产环境：运行打包后的 exe
    script = join(process.resourcesPath, 'backend-engine.exe')
    cmd = script
    args = []
    console.log('Starting Python backend (Prod):', script)
  }

  pyProc = spawn(cmd, args)

  if (pyProc != null) {
    pyProc.stdout.on('data', function (data) {
      console.log('py_stdout: ' + data)
    })
    pyProc.stderr.on('data', function (data) {
      console.log('py_stderr: ' + data)
    })
  }
}

// --- 2. 关闭 Python 后端 ---
const exitPyProc = () => {
  if (pyProc != null) {
    console.log('Killing Python process...')
    pyProc.kill()
    pyProc = null
  }
}

// 【新增】用于存储进入悬浮模式前的窗口状态
let savedWindowState = {
  bounds: null,
  isMaximized: false,
  isFullScreen: false
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 900,
    height: 670,
    show: false,
    autoHideMenuBar: true,
    frame: false, // 无边框
    transparent: true, // 【关键修改】开启透明窗口支持
    hasShadow: false,  // 关闭阴影以避免透明模式下的边框残留
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      webSecurity: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // --- IPC 监听：处理窗口控制 ---

  // 1. 设置窗口置顶与全屏/位置 (用于悬浮模式切换)
  ipcMain.on('set-overlay-mode', (event, { active, bounds }) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (!win) return

    if (active) {
      // === 进入悬浮模式 ===

      // 1. 保存当前状态 (以便退出时恢复)
      savedWindowState.isMaximized = win.isMaximized()
      savedWindowState.isFullScreen = win.isFullScreen()
      if (!savedWindowState.isMaximized && !savedWindowState.isFullScreen) {
        savedWindowState.bounds = win.getBounds()
      }

      // 2. 调整窗口以吸附目标或全屏
      if (bounds) {
        // 如果有目标窗口坐标，移动并调整大小以吸附
        win.setBounds(bounds)
      } else {
        // 否则全屏覆盖
        const primaryDisplay = screen.getPrimaryDisplay()
        const { width, height } = primaryDisplay.workAreaSize
        win.setBounds({ x: 0, y: 0, width, height })
      }

      // 3. 设置置顶和隐藏任务栏
      win.setAlwaysOnTop(true, 'screen-saver') // 确保在最顶层 (比普通置顶更高)
      win.setSkipTaskbar(true) // 在任务栏隐藏

    } else {
      // === 退出悬浮模式 ===

      // 1. 重置属性
      win.setAlwaysOnTop(false)
      win.setSkipTaskbar(false)

      // 2. 恢复之前的窗口状态
      if (savedWindowState.isFullScreen) {
        win.setFullScreen(true)
      } else if (savedWindowState.isMaximized) {
        win.maximize()
      } else if (savedWindowState.bounds) {
        win.setBounds(savedWindowState.bounds)
      } else {
        // 如果没有保存的状态，恢复默认大小
        win.setSize(900, 670)
        win.center()
      }
    }
  })

  // 2. 鼠标穿透控制 (用于悬浮窗模式下点击背景穿透)
  ipcMain.on('set-ignore-mouse', (event, ignore) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    if (win) {
      if (ignore) {
        // ignore = true: 鼠标穿透（点击会点到后面的窗口），forward = true 表示把事件转发给系统
        win.setIgnoreMouseEvents(true, { forward: true })
      } else {
        // ignore = false: 鼠标不穿透（可以点击 Electron 窗口内的按钮/卡片）
        win.setIgnoreMouseEvents(false)
      }
    }
  })

  // 3. 基础窗口控制 (最小化/关闭)
  ipcMain.on('window-min', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    win.minimize()
  })
  ipcMain.on('window-close', (event) => {
    const win = BrowserWindow.fromWebContents(event.sender)
    win.close()
  })


  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.electron')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  createPyProc()
  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('will-quit', () => {
  exitPyProc()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
