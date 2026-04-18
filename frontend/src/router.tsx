import { createBrowserRouter, Navigate } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import TaskList from './pages/TaskList'
import TaskCreate from './pages/TaskCreate'
import TranslationExecution from './pages/TranslationExecution'
import ComparisonReview from './pages/ComparisonReview'
import { ROUTES } from './constants/routes'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <MainLayout />,
    children: [
      {
        index: true,
        element: <Navigate to={ROUTES.TASK_LIST} replace />,
      },
      {
        path: 'tasks',
        element: <TaskList />,
      },
      {
        path: 'tasks/new',
        element: <TaskCreate />,
      },
      {
        path: 'tasks/:id/translate',
        element: <TranslationExecution />,
      },
      {
        path: 'tasks/:id/review',
        element: <ComparisonReview />,
      },
    ],
  },
])
