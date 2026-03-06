import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;

// API functions
export const authAPI = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (data) => api.post('/auth/register', data),
  getMe: () => api.get('/auth/me'),
};

export const usersAPI = {
  getAll: () => api.get('/users'),
  getById: (id) => api.get(`/users/${id}`),
  create: (data) => api.post('/auth/register', data),
  update: (id, data) => api.put(`/users/${id}`, data),
  delete: (id) => api.delete(`/users/${id}`),
};

export const employeesAPI = {
  getAll: () => api.get('/employees'),
  getById: (id) => api.get(`/employees/${id}`),
  create: (data) => api.post('/employees', data),
  update: (id, data) => api.put(`/employees/${id}`, data),
  delete: (id) => api.delete(`/employees/${id}`),
};

export const productsAPI = {
  getAll: (params) => api.get('/products', { params }),
  getCategories: () => api.get('/products/categories'),
  getById: (id) => api.get(`/products/${id}`),
  create: (data) => api.post('/products', data),
  update: (id, data) => api.put(`/products/${id}`, data),
  delete: (id) => api.delete(`/products/${id}`),
};

// Classifications API
export const classificationsAPI = {
  getAll: () => api.get('/classifications'),
  getById: (id) => api.get(`/classifications/${id}`),
  create: (data) => api.post('/classifications', data),
  update: (id, data) => api.put(`/classifications/${id}`, data),
  delete: (id) => api.delete(`/classifications/${id}`),
};

// Categories API
export const categoriesAPI = {
  getAll: () => api.get('/categories'),
  getById: (id) => api.get(`/categories/${id}`),
  create: (data) => api.post('/categories', data),
  update: (id, data) => api.put(`/categories/${id}`, data),
  delete: (id) => api.delete(`/categories/${id}`),
};

export const weightsAPI = {
  record: (data) => api.post('/weights', data),
  getAll: (params) => api.get('/weights', { params }),
  getRecent: (limit = 10) => api.get('/weights/recent', { params: { limit } }),
};

export const dashboardAPI = {
  getStats: () => api.get('/dashboard/stats'),
  getIndividual: (employeeId) => api.get(`/dashboard/individual/${employeeId}`),
  getBreakdown: (startDate, endDate) => api.get('/dashboard/breakdown', { params: { start_date: startDate, end_date: endDate } }),
};

export const payrollAPI = {
  calculate: (data) => api.post('/payroll/calculate', data),
  calculateByProduct: (startDate, endDate) => 
    api.post(`/payroll/calculate-by-product?start_date=${startDate}&end_date=${endDate}`),
  payAll: (startDate, endDate) => 
    api.post(`/payroll/pay-all?start_date=${startDate}&end_date=${endDate}`),
  getAll: (params) => api.get('/payroll', { params }),
  updateStatus: (id, isPaid) => api.put(`/payroll/${id}/status`, { is_paid: isPaid }),
  exportPDF: (startDate, endDate, ratePerKg) => 
    api.get('/export/payroll/pdf', { 
      params: { start_date: startDate, end_date: endDate, rate_per_kg: ratePerKg },
      responseType: 'blob'
    }),
  exportExcel: (startDate, endDate, ratePerKg) => 
    api.get('/export/payroll/excel', { 
      params: { start_date: startDate, end_date: endDate, rate_per_kg: ratePerKg },
      responseType: 'blob'
    }),
};

export const productPricesAPI = {
  getAll: () => api.get('/product-prices'),
  set: (productId, ratePerKg) => api.post('/product-prices', { product_id: productId, rate_per_kg: ratePerKg }),
  update: (productId, ratePerKg) => api.put(`/product-prices/${productId}`, { rate_per_kg: ratePerKg }),
};

export const reportsAPI = {
  getDailyBreakdown: (date, employeeIds) => 
    api.get('/reports/daily-breakdown', { params: { date, employee_ids: employeeIds } }),
  exportPerformancePDF: (period) => 
    api.get('/export/performance/pdf', { 
      params: { period },
      responseType: 'blob'
    }),
  // New export endpoints
  exportDailyExcel: (date, employeeIds) => 
    api.get('/export/reports/daily', { 
      params: { date, employee_ids: employeeIds },
      responseType: 'blob'
    }),
  exportPeriodExcel: () => 
    api.get('/export/reports/period', { 
      responseType: 'blob'
    }),
  exportCategoryExcel: () => 
    api.get('/export/reports/category', { 
      responseType: 'blob'
    }),
  exportStationExcel: () => 
    api.get('/export/reports/station', { 
      responseType: 'blob'
    }),
  exportEmployeeExcel: (employeeId) => 
    api.get(`/export/reports/employee/${employeeId}`, { 
      responseType: 'blob'
    }),
  // Paid payroll reports
  getPaidPayroll: (startDate, endDate) => 
    api.get('/reports/paid-payroll', { params: { start_date: startDate, end_date: endDate } }),
  exportPaidPayrollExcel: (startDate, endDate) => 
    api.get('/export/reports/paid-payroll', { 
      params: { start_date: startDate, end_date: endDate },
      responseType: 'blob'
    }),
};

export const scannerAPI = {
  createSession: (stationName) => api.post('/scanner/session', { station_name: stationName }),
  getSession: (sessionCode) => api.get(`/scanner/session/${sessionCode}`),
  updateWeight: (sessionCode, weightKg, productId) => 
    api.put(`/scanner/session/code/${sessionCode}/weight`, { weight_kg: weightKg, product_id: productId }),
  recordWeight: (sessionCode, employeeQr) => 
    api.post(`/scanner/session/${sessionCode}/record`, { employee_qr: employeeQr }),
  resetSession: (sessionId) => api.put(`/scanner/session/${sessionId}/reset`),
  endSession: (sessionId) => api.delete(`/scanner/session/${sessionId}`),
  getQRCode: (sessionCode, baseUrl) => 
    api.get(`/scanner/qr/${sessionCode}`, { params: { base_url: baseUrl } }),
};

export const scaleAPI = {
  getStatus: () => api.get('/scale/status'),
  configure: (ipAddress, port, protocol = 'tcp', timeout = 5.0) => 
    api.post('/scale/configure', { ip_address: ipAddress, port, protocol, timeout }),
  read: () => api.get('/scale/read'),
  test: (ipAddress, port, timeout = 5.0) => 
    api.post('/scale/test', { ip_address: ipAddress, port, timeout }),
  simulate: (weight) => api.get(`/scale/simulate/${weight}`),
};

// Stations API
export const stationsAPI = {
  getAll: (activeOnly = false) => api.get('/stations', { params: { active_only: activeOnly } }),
  getById: (id) => api.get(`/stations/${id}`),
  create: (data) => api.post('/stations', data),
  update: (id, data) => api.put(`/stations/${id}`, data),
  delete: (id) => api.delete(`/stations/${id}`),
  getStats: (id) => api.get(`/stations/${id}/stats`),
};

// Comparison Reports API
export const comparisonAPI = {
  getEmployeeComparison: (employeeId) => api.get(`/reports/comparison/employee/${employeeId}`),
  getCategoryComparison: () => api.get('/reports/comparison/category'),
  getPeriodComparison: () => api.get('/reports/comparison/period'),
  getStationComparison: () => api.get('/reports/comparison/station'),
};
