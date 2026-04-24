import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { getToken } from "../api/client";

interface Props {
  children: ReactNode;
}

export default function ProtectedRoute({ children }: Props) {
  if (!getToken()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}
