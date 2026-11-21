import type {
  ChatRequest,
  ChatResponse,
  DashboardResponse,
  EditedItemInput,
  MealPlanDetailResponse,
  MealPlanListResponse,
  MealPlanRunResponse,
  PatientProfileInput,
  PreviewEditResponse,
  ReviewSubmitRequest,
  ReviewSubmitResponse,
  SamplePatient,
  SystemStatusResponse,
} from "@/types/api";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    let message = `Lỗi máy chủ (${resp.status})`;
    try {
      const data = await resp.json();
      if (typeof data?.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data?.detail) && data.detail.length > 0) {
        message = data.detail.map((e: { msg?: string }) => e.msg ?? "Dữ liệu không hợp lệ").join("; ");
      }
    } catch {
      // Bỏ qua nếu body không phải JSON
    }
    throw new ApiError(resp.status, message);
  }
  return (await resp.json()) as T;
}

export const apiClient = {
  getSystemStatus: () => requestJson<SystemStatusResponse>("/api/system/status"),
  getGraphMermaid: () => requestJson<{ mermaid: string }>("/api/system/graph-mermaid"),
  getSamplePatients: async (): Promise<SamplePatient[]> => {
    const res = await requestJson<{ patients: SamplePatient[] }>("/api/patients/samples");
    return res.patients;
  },
  runMealPlan: (profile: PatientProfileInput) =>
    requestJson<MealPlanRunResponse>("/api/meal-plans/run", {
      method: "POST",
      body: JSON.stringify(profile),
    }),
  listMealPlans: (status?: string, limit = 60) => {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    params.set("limit", String(limit));
    return requestJson<MealPlanListResponse>(`/api/meal-plans?${params.toString()}`);
  },
  getMealPlanDetail: (id: number) => requestJson<MealPlanDetailResponse>(`/api/meal-plans/${id}`),
  previewEdit: (mealPlanId: number, editedItems: EditedItemInput[]) =>
    requestJson<PreviewEditResponse>(`/api/reviews/${mealPlanId}/preview-edit`, {
      method: "POST",
      body: JSON.stringify({ edited_items: editedItems }),
    }),
  submitReview: (mealPlanId: number, payload: ReviewSubmitRequest) =>
    requestJson<ReviewSubmitResponse>(`/api/reviews/${mealPlanId}/submit`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getDashboard: (params: {
    startDate?: string;
    endDate?: string;
    condition?: string | null;
    includeSynthetic?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params.startDate) qs.set("start_date", params.startDate);
    if (params.endDate) qs.set("end_date", params.endDate);
    if (params.condition) qs.set("condition", params.condition);
    qs.set("include_synthetic", String(params.includeSynthetic ?? true));
    return requestJson<DashboardResponse>(`/api/dashboard?${qs.toString()}`);
  },
  getDashboardCsvUrl: (params: {
    startDate?: string;
    endDate?: string;
    condition?: string | null;
    includeSynthetic?: boolean;
  }) => {
    const qs = new URLSearchParams();
    if (params.startDate) qs.set("start_date", params.startDate);
    if (params.endDate) qs.set("end_date", params.endDate);
    if (params.condition) qs.set("condition", params.condition);
    qs.set("include_synthetic", String(params.includeSynthetic ?? true));
    return `/api/dashboard/export.csv?${qs.toString()}`;
  },
  sendChat: (payload: ChatRequest) =>
    requestJson<ChatResponse>("/api/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
