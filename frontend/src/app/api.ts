const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getAuthToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("token");
  }
  return null;
}

export function saveAuthToken(token: string): void {
  if (typeof window !== "undefined") {
    localStorage.setItem("token", token);
  }
}

export function removeAuthToken(): void {
  if (typeof window !== "undefined") {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  }
}

export function getCurrentUser(): any | null {
  if (typeof window !== "undefined") {
    const userStr = localStorage.getItem("user");
    if (userStr) {
      try {
        return JSON.parse(userStr);
      } catch {
        return null;
      }
    }
  }
  return null;
}

async function request(endpoint: string, method: string = "GET", body: any = null) {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const token = getAuthToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const config: RequestInit = {
    method,
    headers,
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${endpoint}`, config);

  if (response.status === 204) {
    return null;
  }

  const data = await response.json();

  if (!response.ok) {
    if (response.status === 401 && !endpoint.includes("/auth/login")) {
      removeAuthToken();
      if (typeof window !== "undefined") {
        window.location.reload();
      }
    }
    throw new Error(data.detail || "Something went wrong");
  }

  return data;
}

export const api = {
  // Auth
  register: (payload: any) => request("/api/auth/register", "POST", payload),
  login: (payload: any) => request("/api/auth/login", "POST", payload),

  // Products
  getProducts: (params?: { category?: string; stock_status?: string; search?: string; sort_by?: string; sort_order?: string }) => {
    const query = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, val]) => {
        if (val) query.append(key, val);
      });
    }
    return request(`/api/products?${query.toString()}`);
  },
  createProduct: (payload: any) => request("/api/products", "POST", payload),
  updateProduct: (id: string, payload: any) => request(`/api/products/${id}`, "PUT", payload),
  deleteProduct: (id: string) => request(`/api/products/${id}`, "DELETE"),

  // Recommendations
  getRecommendations: (statusFilter: string = "PENDING") => request(`/api/recommendations?status_filter=${statusFilter}`),
  getRecommendation: (id: string) => request(`/api/recommendations/${id}`),
  triggerAnalysis: (productId: string) => request(`/api/recommendations/analyze/${productId}`, "POST"),
  approveRecommendation: (id: string) => request(`/api/recommendations/${id}/approve`, "POST"),
  rejectRecommendation: (id: string, reason: string) => request(`/api/recommendations/${id}/reject`, "POST", { reason }),
  modifyRecommendation: (id: string, price: number) => request(`/api/recommendations/${id}/modify`, "POST", { price }),

  // Config
  getConfig: () => request("/api/config"),
  updateConfig: (payload: any) => request("/api/config", "PUT", payload),

  // Audits
  getAudits: () => request("/api/audits"),
};
