import { Navigate } from 'react-router-dom';
import { authService } from '../services/auth';

export default function PrivateRoute({ children }: { children: React.ReactNode }) {
  if (!authService.isAuthenticated()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
