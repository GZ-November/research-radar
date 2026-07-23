import { Route, Routes } from 'react-router'
import { AppStoreProvider } from '@/store/AppStore'
import { AppShell } from '@/components/radar/AppShell'
import Home from '@/pages/Home'
import ActionCenter from '@/pages/ActionCenter'
import ImpactWorkspace from '@/pages/ImpactWorkspace'
import Ledger from '@/pages/Ledger'
import CasePage from '@/pages/CasePage'
import SettingsPage from '@/pages/SettingsPage'

export default function App() {
  return (
    <AppStoreProvider>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Home />} />
          <Route path="/actions" element={<ActionCenter />} />
          <Route path="/radar" element={<ImpactWorkspace />} />
          <Route path="/ledger" element={<Ledger />} />
          <Route path="/case" element={<CasePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Home />} />
        </Route>
      </Routes>
    </AppStoreProvider>
  )
}
