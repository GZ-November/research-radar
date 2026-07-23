import { useState } from 'react'
import { Outlet } from 'react-router'
import { Menu } from 'lucide-react'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { Toaster } from '@/components/ui/sonner'
import { SidebarContent } from './Sidebar'
import { GlobalConfirmDialog } from './GlobalConfirmDialog'

// 全局外壳：≥1024px 固定 264px 深色侧边栏；窄屏折叠为抽屉
export function AppShell() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  return (
    <div className="flex min-h-screen bg-ground">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-[264px] lg:block">
        <SidebarContent />
      </aside>

      {/* 窄屏顶栏 + 抽屉 */}
      <div className="fixed inset-x-0 top-0 z-40 flex h-12 items-center gap-2 border-b border-sep bg-white/90 px-3 backdrop-blur lg:hidden">
        <button
          aria-label="打开导航"
          onClick={() => setDrawerOpen(true)}
          className="flex size-8 items-center justify-center rounded-[8px] text-ls transition-colors hover:bg-black/[0.05]"
        >
          <Menu className="size-5" />
        </button>
        <span className="t-b2e text-lp">Research Radar</span>
      </div>
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" className="w-[280px] border-0 bg-side p-0">
          <SheetTitle className="sr-only">导航</SheetTitle>
          <SidebarContent onNavigate={() => setDrawerOpen(false)} />
        </SheetContent>
      </Sheet>

      <main className="min-w-0 flex-1 pt-12 lg:pl-[264px] lg:pt-0">
        <div className="mx-auto max-w-[1200px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </div>
      </main>

      <GlobalConfirmDialog />
      <Toaster position="top-center" richColors closeButton={false} />
    </div>
  )
}
