import { createBrowserRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/app-shell'
import { ChatPage } from '@/pages/chat-page'
import { SettingsPage } from '@/pages/settings-page'
import { UploadsPage } from '@/pages/uploads-page'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <ChatPage /> },
      { path: 'uploads', element: <UploadsPage />,
      },
      { path: 'settings', element: <SettingsPage /> },
    ],
  },
])
