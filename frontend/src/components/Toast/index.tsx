import { message } from 'antd'

interface ToastOptions {
  duration?: number
  onClose?: () => void
}

class Toast {
  private static defaultDuration = 3

  static success(content: string, options?: ToastOptions) {
    message.success({
      content,
      duration: options?.duration ?? this.defaultDuration,
      onClose: options?.onClose,
    })
  }

  static error(content: string, options?: ToastOptions) {
    message.error({
      content,
      duration: options?.duration ?? 5,
      onClose: options?.onClose,
    })
  }

  static warning(content: string, options?: ToastOptions) {
    message.warning({
      content,
      duration: options?.duration ?? 4,
      onClose: options?.onClose,
    })
  }

  static info(content: string, options?: ToastOptions) {
    message.info({
      content,
      duration: options?.duration ?? this.defaultDuration,
      onClose: options?.onClose,
    })
  }

  static loading(content: string) {
    return message.loading({
      content,
      duration: 0,
    })
  }
}

export default Toast
