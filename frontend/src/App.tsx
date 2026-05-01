import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import MainLayout from './components/layout/MainLayout';
import Dashboard from './pages/Dashboard';
import Documents from './pages/Documents';
import Voice from './pages/Voice';
import Login from './pages/Login';
import AdminAudit from './pages/AdminAudit';

// Simple Protected Route
const PrivateRoute = () => {
  const token = localStorage.getItem('auth_token');
  return token ? <Outlet /> : <Navigate to="/login" replace />;
};

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public Routes */}
        <Route path="/login" element={<Login />} />

        {/* Main Layout Routes */}
        <Route element={<MainLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/voice" element={<Voice />} />
        </Route>

        {/* Admin/Protected Routes */}
        <Route element={<MainLayout />}> {/* Admin can share MainLayout or have its own */}
          <Route element={<PrivateRoute />}>
            <Route path="/admin/audit" element={<AdminAudit />} />
          </Route>
        </Route>

      </Routes>
    </BrowserRouter>
  );
}

export default App;
