import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 20000,
});

export const getHealth = async () => {
  const { data } = await api.get("/health");
  return data;
};

export const listPlans = async () => {
  const { data } = await api.get("/plans");
  return data.data;
};

export const createPlan = async (name) => {
  const { data } = await api.post("/plans", { name });
  return data.data;
};

export const getTable1 = async (planId) => {
  const { data } = await api.get(`/plans/${planId}/table1`);
  return data.data;
};

export const transferTable1 = async (planId, selections) => {
  const { data } = await api.post(`/plans/${planId}/table1/transfer`, { selections });
  return data.data;
};

export const getTable2 = async (planId) => {
  const { data } = await api.get(`/plans/${planId}/table2`);
  return data.data;
};

export const createTable2Element = async (planId, payload) => {
  const { data } = await api.post(`/plans/${planId}/table2/elements`, payload);
  return data.data;
};

export const updateTable2Element = async (planId, elementId, payload) => {
  const { data } = await api.patch(`/plans/${planId}/table2/elements/${elementId}`, payload);
  return data.data;
};

export const deleteTable2Element = async (planId, elementId) => {
  const { data } = await api.delete(`/plans/${planId}/table2/elements/${elementId}`);
  return data.data;
};

export const getTable3 = async (planId) => {
  const { data } = await api.get(`/plans/${planId}/table3`);
  return data.data;
};

export const validatePlan = async (planId) => {
  const { data } = await api.post(`/plans/${planId}/validate`);
  return data;
};

export const updatePlanStatus = async (planId, status) => {
  const { data } = await api.patch(`/plans/${planId}/status`, { status });
  return data.data;
};

export const getExportUrl = (planId) => `/api/v1/plans/${planId}/export/xlsx`;

export const getErrorMessage = (error, fallbackMessage) =>
  error?.response?.data?.detail || error?.message || fallbackMessage;

export default api;
