// ============================================================================
// API Client для работы с FastAPI Backend
// ============================================================================

const API_BASE_URL = window.location.hostname === 'localhost' 
  ? 'http://localhost:8000' 
  : 'http://python_backend:8000';

// ────────────────────────────────────────────────────────────────────────────
// Token Management
// ────────────────────────────────────────────────────────────────────────────

function getToken() {
  return localStorage.getItem('auth_token');
}

function setToken(token) {
  localStorage.setItem('auth_token', token);
}

function clearToken() {
  localStorage.removeItem('auth_token');
}

function isAuthenticated() {
  return !!getToken();
}

// ────────────────────────────────────────────────────────────────────────────
// HTTP Helper
// ────────────────────────────────────────────────────────────────────────────

async function apiRequest(endpoint, options = {}) {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  };

  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const config = {
    ...options,
    headers
  };

  try {
    const response = await fetch(url, config);
    
    // Unauthorized - clear token
    if (response.status === 401) {
      clearToken();
      throw new Error('Необходима авторизация');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('API Request failed:', error);
    throw error;
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Auth API
// ────────────────────────────────────────────────────────────────────────────

async function login(username, password) {
  const formData = new URLSearchParams();
  formData.append('username', username);
  formData.append('password', password);

  const response = await fetch(`${API_BASE_URL}/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  const data = await response.json();
  setToken(data.access_token);
  return data;
}

async function register(username, password) {
  return apiRequest('/register', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
}

function logout() {
  clearToken();
  window.location.reload();
}

// ────────────────────────────────────────────────────────────────────────────
// Cards API
// ────────────────────────────────────────────────────────────────────────────

async function getCards(params = {}) {
  const queryString = new URLSearchParams(params).toString();
  const endpoint = queryString ? `/cards?${queryString}` : '/cards';
  return apiRequest(endpoint);
}

async function getCard(id) {
  return apiRequest(`/cards/${id}`);
}

async function createCard(cardData) {
  return apiRequest('/cards', {
    method: 'POST',
    body: JSON.stringify(cardData)
  });
}

// ────────────────────────────────────────────────────────────────────────────
// Persons API (Alphabetical Index)
// ────────────────────────────────────────────────────────────────────────────

async function getAlphabeticalIndex() {
  return apiRequest('/api/persons/alphabetical');
}

// ────────────────────────────────────────────────────────────────────────────
// Chat / RAG API
// ────────────────────────────────────────────────────────────────────────────

async function sendChatMessage(query) {
  return apiRequest('/chat', {
    method: 'POST',
    body: JSON.stringify({ query })
  });
}

// ────────────────────────────────────────────────────────────────────────────
// Document Upload
// ────────────────────────────────────────────────────────────────────────────

async function uploadDocument(file, personId) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('person_id', personId);

  const token = getToken();
  const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

  const response = await fetch(`${API_BASE_URL}/upload_document`, {
    method: 'POST',
    headers,
    body: formData
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Upload failed');
  }

  return await response.json();
}

// ────────────────────────────────────────────────────────────────────────────
// Stats API
// ────────────────────────────────────────────────────────────────────────────

async function getStats() {
  return apiRequest('/api/stats');
}
