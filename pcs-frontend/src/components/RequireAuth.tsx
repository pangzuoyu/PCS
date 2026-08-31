import { ReactNode, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';

export default function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuth((s) => s.accessToken);
  const nav = useNavigate();

  useEffect(() => {
    if (!token) {
      nav('/login', { replace: true });
    }
  }, [token, nav]);

  return token ? <>{children}</> : null;
}
