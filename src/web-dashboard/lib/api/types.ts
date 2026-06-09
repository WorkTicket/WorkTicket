export interface Customer {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  address?: string;
}

export interface Job {
  id: string;
  description: string;
  address: string;
  status: string;
  customer_id: string;
  created_at?: string;
}

export interface Estimate {
  id: string;
  title: string;
  status: string;
  created_at?: string;
  total: number;
}

export interface Quote {
  quote_id: string;
  job_id: string;
  status: string;
  total_amount: number;
}

export interface CurrentUserResponse {
  user_id: string;
  email: string;
  name: string;
  role: string;
  company_id: string;
}
