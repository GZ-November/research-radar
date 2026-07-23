import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { useAppStore } from '@/store/AppStore'
import { Button } from './Button'

// 全局确认对话框：标题 操作确认，粗体操作名 + 说明正文 + 主按钮（动态文案）+ 取消
export function GlobalConfirmDialog() {
  const { confirmState, resolveConfirm } = useAppStore()
  const open = confirmState !== null
  return (
    <AlertDialog open={open} onOpenChange={(v) => { if (!v) resolveConfirm(false) }}>
      <AlertDialogContent className="w-[360px] max-w-[calc(100vw-32px)] rounded-[16px] border-0 p-4 shadow-[0_4px_15px_rgba(0,0,0,0.15)]">
        <AlertDialogHeader>
          <AlertDialogTitle className="t-t2e text-lp">
            {confirmState?.title ?? '操作确认'}
          </AlertDialogTitle>
          <AlertDialogDescription className="t-b2 text-lp">
            <strong className="t-b2e">{confirmState?.actionName}</strong>
            <br />
            {confirmState?.description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className="mt-2 flex-row justify-end gap-2 sm:justify-end">
          <Button variant="secondary" size={32} onClick={() => resolveConfirm(false)}>
            取消
          </Button>
          <Button
            variant="primary"
            size={32}
            danger={confirmState?.danger}
            onClick={() => resolveConfirm(true)}
          >
            {confirmState?.confirmLabel ?? '确认'}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
