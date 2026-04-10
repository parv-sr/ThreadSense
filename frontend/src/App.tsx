import { RouterProvider } from 'react-router-dom'
import { Toaster } from 'sonner'
import { router } from './routes'

const App = () => (
  <>
    <RouterProvider router={router} />
    <Toaster richColors position='top-right' />
  </>
)

export default App
