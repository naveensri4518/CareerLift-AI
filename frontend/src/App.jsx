import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
import { AppLayout } from './components/AppLayout.jsx'
import Landing from './pages/Landing.jsx'
import Register from './pages/Register.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Practice from './pages/Practice.jsx'
import InterviewStudio from './pages/studio/InterviewStudio.jsx'
import InterviewSession from './pages/studio/InterviewSession.jsx'
import CodingArena from './pages/coding/CodingArena.jsx'
import CodingProblem from './pages/coding/CodingProblem.jsx'
import AssessmentLanding from './pages/assessment/AssessmentLanding.jsx'
import AssessmentAttempt from './pages/assessment/AssessmentAttempt.jsx'
import AssessmentResult from './pages/assessment/AssessmentResult.jsx'
import AssessmentHistory from './pages/assessment/AssessmentHistory.jsx'
import SysDesignAcademy from './pages/sysdesign/SysDesignAcademy.jsx'
import SysDesignScenario from './pages/sysdesign/SysDesignScenario.jsx'
import SysDesignWorkspace from './pages/sysdesign/SysDesignWorkspace.jsx'
import SysDesignResult from './pages/sysdesign/SysDesignResult.jsx'
import SysDesignHistory from './pages/sysdesign/SysDesignHistory.jsx'
import Progress from './pages/Progress.jsx'
import Misconceptions from './pages/Misconceptions.jsx'
import Planner from './pages/Planner.jsx'
import Reports from './pages/Reports.jsx'

function Protected({ children }) {
  const { isAuthed } = useAuth()
  if (!isAuthed) return <Navigate to="/register" replace />
  return <AppLayout>{children}</AppLayout>
}

export default function App() {
  const { isAuthed } = useAuth()
  return (
    <Routes>
      <Route path="/" element={isAuthed ? <Navigate to="/app" replace /> : <Landing />} />
      <Route path="/register" element={isAuthed ? <Navigate to="/app" replace /> : <Register />} />

      <Route path="/app" element={<Protected><Dashboard /></Protected>} />
      <Route path="/app/interview" element={<Protected><InterviewStudio /></Protected>} />
      <Route path="/app/interview/session/:id" element={<Protected><InterviewSession /></Protected>} />
      <Route path="/app/coding" element={<Protected><CodingArena /></Protected>} />
      <Route path="/app/coding/:id" element={<Protected><CodingProblem /></Protected>} />
      <Route path="/app/assessment" element={<Protected><AssessmentLanding /></Protected>} />
      <Route path="/app/assessment/attempt/:id" element={<Protected><AssessmentAttempt /></Protected>} />
      <Route path="/app/assessment/result/:id" element={<Protected><AssessmentResult /></Protected>} />
      <Route path="/app/assessment/history" element={<Protected><AssessmentHistory /></Protected>} />
      <Route path="/app/sysdesign" element={<Protected><SysDesignAcademy /></Protected>} />
      <Route path="/app/sysdesign/scenario/:id" element={<Protected><SysDesignScenario /></Protected>} />
      <Route path="/app/sysdesign/attempt/:id" element={<Protected><SysDesignWorkspace /></Protected>} />
      <Route path="/app/sysdesign/result/:id" element={<Protected><SysDesignResult /></Protected>} />
      <Route path="/app/sysdesign/history" element={<Protected><SysDesignHistory /></Protected>} />
      <Route path="/app/practice" element={<Protected><Practice /></Protected>} />
      <Route path="/app/progress" element={<Protected><Progress /></Protected>} />
      <Route path="/app/misconceptions" element={<Protected><Misconceptions /></Protected>} />
      <Route path="/app/planner" element={<Protected><Planner /></Protected>} />
      <Route path="/app/reports" element={<Protected><Reports /></Protected>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
