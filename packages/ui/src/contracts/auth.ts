/** Mirrors `services/api/app/main.py` `LoginRequest`/`get_current_user`. */

export interface LoginRequest {
  email: string;
  password: string;
  organization_id: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
}

export interface MeResponse {
  user_id: string;
  organization_id: string;
  roles: string[];
}
