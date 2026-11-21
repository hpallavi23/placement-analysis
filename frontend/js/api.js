/**
 * NXTSTEP Centralized API Client
 * Base URL: http://127.0.0.1:8000/api/v1
 *
 * Responsibilities:
 * - Centralized fetch wrapper with automatic token management
 * - Authorization: Bearer <token> attachment on protected requests
 * - Handling JSON and OAuth2 form-data payloads
 * - Graceful handling of HTTP errors, Pydantic validation details, and 401s
 * - Authentication (login, registration, /auth/me, logout)
 * - Student Profile CRUD (/profile/)
 */

(function (window) {
  "use strict";

  const DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1";
  const TOKEN_STORAGE_KEY = "nxtstep_access_token";

  function resolveBaseUrl() {
    if (typeof window !== "undefined" && window.NXTSTEP_API_BASE_URL && typeof window.NXTSTEP_API_BASE_URL === "string") {
      const trimmed = window.NXTSTEP_API_BASE_URL.trim();
      if (trimmed) {
        return trimmed;
      }
    }
    return DEFAULT_BASE_URL;
  }

  class ApiClient {
    constructor(baseUrl) {
      this._customBaseUrl = baseUrl ? String(baseUrl).trim().replace(/\/+$/, "") : null;
    }

    get baseUrl() {
      if (this._customBaseUrl) {
        return this._customBaseUrl;
      }
      return resolveBaseUrl().replace(/\/+$/, "");
    }

    set baseUrl(url) {
      this._customBaseUrl = url ? String(url).trim().replace(/\/+$/, "") : null;
    }

    /**
     * Retrieve the stored JWT access token from localStorage.
     */
    getToken() {
      try {
        return localStorage.getItem(TOKEN_STORAGE_KEY);
      } catch (err) {
        console.warn("Storage access failed:", err);
        return null;
      }
    }

    /**
     * Persist or clear the JWT access token.
     */
    setToken(token) {
      try {
        if (token) {
          localStorage.setItem(TOKEN_STORAGE_KEY, token);
        } else {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
        }
      } catch (err) {
        console.warn("Storage write failed:", err);
      }
    }

    /**
     * Clear the stored JWT token.
     */
    clearToken() {
      this.setToken(null);
    }

    /**
     * Check if a token is currently present.
     */
    isAuthenticated() {
      return Boolean(this.getToken());
    }

    /**
     * Core fetch wrapper.
     */
    async request(endpoint, options = {}) {
      const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
      const url = `${this.baseUrl}${cleanEndpoint}`;

      const headers = new Headers(options.headers || {});

      // Automatically attach Bearer token to protected endpoints if available
      const token = this.getToken();
      if (token && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${token}`);
      }

      const fetchConfig = {
        ...options,
        headers,
      };

      let response;
      try {
        response = await fetch(url, fetchConfig);
      } catch (netErr) {
        const error = new Error(
          `Unable to connect to NXTSTEP backend at ${this.baseUrl}. Please verify the server is running.`
        );
        error.isNetworkError = true;
        throw error;
      }

      // Handle 401 Unauthorized: clear token and notify application (except for login itself)
      if (response.status === 401 && !cleanEndpoint.includes("/auth/login")) {
        this.clearToken();
        if (typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("nxtstep:unauthorized"));
        }
      }

      // Parse response body
      let data = null;
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        try {
          data = await response.json();
        } catch (jsonErr) {
          data = null;
        }
      } else {
        try {
          data = await response.text();
        } catch (textErr) {
          data = null;
        }
      }

      if (!response.ok) {
        let message = `Request failed (HTTP ${response.status})`;

        if (data && typeof data === "object") {
          if (data.detail) {
            if (Array.isArray(data.detail)) {
              // FastAPI/Pydantic validation errors array
              message = data.detail
                .map(err => {
                  const loc = Array.isArray(err.loc) ? err.loc.slice(1).join(".") : "";
                  return loc ? `${loc}: ${err.msg}` : err.msg;
                })
                .join("; ");
            } else if (typeof data.detail === "string") {
              message = data.detail;
            }
          } else if (data.message) {
            message = data.message;
          }
        }

        const error = new Error(message);
        error.status = response.status;
        error.data = data;
        throw error;
      }

      return data;
    }

    // =========================================================================
    // Authentication Endpoints
    // =========================================================================

    /**
     * Register a new user account.
     * Backend: POST /api/v1/auth/register (JSON)
     * Returns UserResponse: { id, email, is_active, created_at }
     */
    async register(email, password) {
      return this.request("/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: String(email).trim().toLowerCase(),
          password: String(password),
        }),
      });
    }

    /**
     * Log in with OAuth2 form-data credentials.
     * Backend: POST /api/v1/auth/login (application/x-www-form-urlencoded)
     * Body: username=<email>&password=<password>
     * Returns Token: { access_token, token_type }
     */
    async login(username, password) {
      const params = new URLSearchParams();
      params.append("username", String(username).trim().toLowerCase());
      params.append("password", String(password));

      const data = await this.request("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params.toString(),
      });

      if (data && data.access_token) {
        this.setToken(data.access_token);
      }

      return data;
    }

    /**
     * Retrieve the currently authenticated user's account details.
     * Backend: GET /api/v1/auth/me (Protected)
     * Returns UserResponse: { id, email, is_active, created_at }
     */
    async getCurrentUser() {
      return this.request("/auth/me", { method: "GET" });
    }

    /**
     * Clear token and trigger application logout event.
     */
    logout() {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("nxtstep:logout"));
      }
    }

    // =========================================================================
    // Student Profile Endpoints
    // =========================================================================

    /**
     * Fetch the authenticated user's student profile.
     * Backend: GET /api/v1/profile/ (Protected)
     * Returns StudentProfileResponse or throws 404 if not found.
     */
    async getProfile() {
      return this.request("/profile/", { method: "GET" });
    }

    /**
     * Create the student profile (first time).
     * Backend: POST /api/v1/profile/ (Protected, JSON)
     * Payload: { full_name, college?, branch?, graduation_year?, cgpa? }
     * Returns StudentProfileResponse (HTTP 201)
     */
    async createProfile(profileData) {
      return this.request("/profile/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profileData),
      });
    }

    /**
     * Update an existing student profile.
     * Backend: PUT /api/v1/profile/ (Protected, JSON)
     * Payload: Partial { full_name?, college?, branch?, graduation_year?, cgpa? }
     * Returns StudentProfileResponse
     */
    async updateProfile(profileData) {
      return this.request("/profile/", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profileData),
      });
    }

    // =========================================================================
    // Assessment & Readiness Endpoints
    // =========================================================================

    /**
     * Submit a new placement readiness assessment.
     * Backend: POST /api/v1/assessments/ (Protected, JSON)
     * Payload: { aptitude_score, technical_score, communication_score, problem_solving_score }
     * Returns AssessmentResponse (HTTP 201):
     *   { id, user_id, aptitude_score, technical_score, communication_score, problem_solving_score, readiness_score, created_at }
     */
    async createAssessment(assessmentData) {
      return this.request("/assessments/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          aptitude_score: Number(assessmentData.aptitude_score),
          technical_score: Number(assessmentData.technical_score),
          communication_score: Number(assessmentData.communication_score),
          problem_solving_score: Number(assessmentData.problem_solving_score),
        }),
      });
    }

    /**
     * Fetch the user's latest assessment.
     * Backend: GET /api/v1/assessments/latest (Protected)
     * Returns AssessmentResponse or throws HTTP 404 error if none found.
     */
    async getLatestAssessment() {
      return this.request("/assessments/latest", { method: "GET" });
    }

    /**
     * Fetch the user's assessment history.
     * Backend: GET /api/v1/assessments/history (Protected)
     * Returns list of AssessmentResponse sorted descending by created_at.
     */
    async getAssessmentHistory() {
      return this.request("/assessments/history", { method: "GET" });
    }

    /**
     * Fetch the dashboard summary for the authenticated user.
     * Backend: GET /api/v1/dashboard/summary (Protected)
     * Returns DashboardResponse including student, readiness, skills_overview, role_readiness, roadmap_progress.
     */
    async getDashboardSummary() {
      return this.request("/dashboard/summary", { method: "GET" });
    }

    // =========================================================================
    // Skills Endpoints
    // =========================================================================

    /**
     * Retrieve all saved skills for the authenticated user.
     * Backend: GET /api/v1/skills/ (Protected)
     * Returns list of SkillResponse: [{ id, user_id, skill_name, proficiency }]
     */
    async getSkills() {
      return this.request("/skills/", { method: "GET" });
    }

    /**
     * Upsert (add or update) an individual skill proficiency level.
     * Backend: POST /api/v1/skills/ (Protected, JSON)
     * Payload: { skill_name, proficiency }
     * Returns SkillResponse: { id, user_id, skill_name, proficiency }
     */
    async saveSkill(skillData) {
      return this.request("/skills/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skill_name: String(skillData.skill_name).trim(),
          proficiency: Number(skillData.proficiency),
        }),
      });
    }

    /**
     * Alias for saveSkill to support addSkill calls.
     */
    async addSkill(skillData) {
      return this.saveSkill(skillData);
    }

    // =========================================================================
    // Skill Evidence Endpoints
    // =========================================================================

    /**
     * Submit evidence for a specific skill.
     * Backend: POST /api/v1/skills/{skill_id}/evidence (Protected, JSON)
     * Payload: { evidence_type, title, url, description? }
     * Returns EvidenceResponse (HTTP 201)
     */
    async submitSkillEvidence(skillId, evidenceData) {
      const payload = {
        evidence_type: String(evidenceData.evidence_type).trim(),
        title: String(evidenceData.title).trim(),
        url: String(evidenceData.url).trim(),
      };
      if (evidenceData.description && String(evidenceData.description).trim()) {
        payload.description = String(evidenceData.description).trim();
      }
      return this.request(`/skills/${skillId}/evidence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }

    /**
     * Retrieve all evidence submissions for a specific skill.
     * Backend: GET /api/v1/skills/{skill_id}/evidence (Protected)
     * Returns list of EvidenceResponse
     */
    async getSkillEvidence(skillId) {
      return this.request(`/skills/${skillId}/evidence`, { method: "GET" });
    }

    /**
     * Delete a pending evidence submission owned by the student.
     * Backend: DELETE /api/v1/skills/evidence/{evidence_id} (Protected)
     * Returns { message, id }
     */
    async deleteSkillEvidence(evidenceId) {
      return this.request(`/skills/evidence/${evidenceId}`, { method: "DELETE" });
    }

    // =========================================================================
    // Roadmap Endpoints
    // =========================================================================

    /**
     * Fetch existing roadmap tasks for the specified role.
     * Backend: GET /api/v1/roadmaps/{role} (Protected)
     * Returns list of RoadmapTaskResponse
     */
    async getRoadmap(role) {
      const encodedRole = encodeURIComponent(String(role).trim());
      return this.request(`/roadmaps/${encodedRole}`, { method: "GET" });
    }

    /**
     * Generate or update roadmap tasks for the specified role based on saved skills.
     * Backend: POST /api/v1/roadmaps/{role}/generate (Protected)
     * Returns list of RoadmapTaskResponse
     */
    async generateRoadmap(role) {
      const encodedRole = encodeURIComponent(String(role).trim());
      return this.request(`/roadmaps/${encodedRole}/generate`, { method: "POST" });
    }

    /**
     * Mark a roadmap task as completed.
     * Backend: PUT /api/v1/roadmaps/tasks/{task_id}/complete (Protected)
     * Returns RoadmapTaskCompleteResponse: { message, task }
     */
    async completeRoadmapTask(taskId) {
      return this.request(`/roadmaps/tasks/${taskId}/complete`, { method: "PUT" });
    }

    // =========================================================================
    // Opportunities Endpoints
    // =========================================================================

    /**
     * Fetch evaluated benchmark placement opportunities for the authenticated student.
     * Backend: GET /api/v1/opportunities/ (Protected)
     * Returns list of OpportunityMatchResult
     */
    async getOpportunities() {
      return this.request("/opportunities/", { method: "GET" });
    }

    /**
     * Fetch evaluated details for a specific benchmark opportunity by ID.
     * Backend: GET /api/v1/opportunities/{id} (Protected)
     * Returns OpportunityMatchResult
     */
    async getOpportunityDetail(opportunityId) {
      return this.request(`/opportunities/${opportunityId}`, { method: "GET" });
    }
  }

  // Export singleton on window.api
  const apiInstance = new ApiClient();
  window.api = apiInstance;
  window.ApiClient = ApiClient;

})(typeof window !== "undefined" ? window : globalThis);
