"use client";

import React, { useState, useEffect } from "react";
import { api, getAuthToken, saveAuthToken, removeAuthToken, getCurrentUser } from "./api";

export default function Home() {
  // Global Rupee conversion
  const USD_TO_INR = 84.0;
  const formatCurrency = (usdVal: any) => {
    const usd = typeof usdVal === "string" ? parseFloat(usdVal) : usdVal;
    if (isNaN(usd) || usd === null || usd === undefined) return "₹0.00";
    const inr = usd * USD_TO_INR;
    return `₹${inr.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  };

  // Auth & View state
  const [viewMode, setViewMode] = useState<"landing" | "app">("landing");
  const [isAuth, setIsAuth] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("ADMIN");
  const [orgName, setOrgName] = useState("");
  const [orgIdInput, setOrgIdInput] = useState("");
  const [authError, setAuthError] = useState("");
  const [user, setUser] = useState<any>(null);

  // Dashboard state
  const [activeTab, setActiveTab] = useState<"catalog" | "recommendations" | "audits" | "config">("catalog");
  const [loading, setLoading] = useState(false);
  
  // Data state
  const [products, setProducts] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [audits, setAudits] = useState<any[]>([]);
  const [config, setConfig] = useState<any>(null);
  
  // Filter state
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [stockFilter, setStockFilter] = useState("");
  const [sortBy, setSortBy] = useState("sku");
  const [sortOrder, setSortOrder] = useState("asc");

  // Selection states
  const [selectedProduct, setSelectedProduct] = useState<any>(null);
  const [selectedRec, setSelectedRec] = useState<any>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [overridePrice, setOverridePrice] = useState("");
  const [showOverrideForm, setShowOverrideForm] = useState(false);

  // Modal states for Product CRUD (Admin Only)
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<any>(null);

  // Add/Edit Form states
  const [sku, setSku] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("electronics");
  const [currentPrice, setCurrentPrice] = useState("");
  const [cogs, setCogs] = useState("");
  const [inventoryCount, setInventoryCount] = useState("");
  const [marginThreshold, setMarginThreshold] = useState("0.15");
  
  // Admin config form state
  const [configThreshold, setConfigThreshold] = useState(0.85);
  const [electronicsFloor, setElectronicsFloor] = useState(0.10);
  const [apparelFloor, setApparelFloor] = useState(0.20);
  const [homeGoodsFloor, setHomeGoodsFloor] = useState(0.15);
  const [configSuccess, setConfigSuccess] = useState(false);

  // Pipeline triggers
  const [analysingId, setAnalysingId] = useState<string | null>(null);

  // Check auth on load
  useEffect(() => {
    const token = getAuthToken();
    const currentUser = getCurrentUser();
    if (token && currentUser) {
      setIsAuth(true);
      setUser(currentUser);
    }
  }, []);

  // Fetch data depending on tab
  useEffect(() => {
    if (!isAuth) return;
    fetchData();
  }, [isAuth, activeTab, categoryFilter, stockFilter, search, sortBy, sortOrder]);

  const fetchData = async () => {
    setLoading(true);
    try {
      if (activeTab === "catalog") {
        const prodData = await api.getProducts({
          category: categoryFilter,
          stock_status: stockFilter,
          search,
          sort_by: sortBy,
          sort_order: sortOrder
        });
        setProducts(prodData);
      } else if (activeTab === "recommendations") {
        const recData = await api.getRecommendations("PENDING");
        setRecommendations(recData);
      } else if (activeTab === "audits") {
        const auditData = await api.getAudits();
        setAudits(auditData);
      } else if (activeTab === "config") {
        const confData = await api.getConfig();
        setConfig(confData);
        setConfigThreshold(confData.auto_execute_threshold);
        setElectronicsFloor(confData.category_margin_floors.electronics || 0.10);
        setApparelFloor(confData.category_margin_floors.apparel || 0.20);
        setHomeGoodsFloor(confData.category_margin_floors["home goods"] || 0.15);
      }
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    try {
      let data;
      if (authMode === "login") {
        data = await api.login({ email, password });
      } else {
        const payload: any = {
          email,
          password,
          full_name: fullName,
          role,
        };
        if (orgIdInput) payload.org_id = orgIdInput;
        else if (orgName) payload.org_name = orgName;
        else {
          setAuthError("Please specify organization name or ID.");
          return;
        }
        data = await api.register(payload);
      }
      saveAuthToken(data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));
      setUser(data.user);
      setIsAuth(true);
      // Reset forms
      setEmail("");
      setPassword("");
      setFullName("");
      setOrgName("");
      setOrgIdInput("");
    } catch (err: any) {
      setAuthError(err.message || "Authentication failed.");
    }
  };

  const handleLogout = () => {
    removeAuthToken();
    setIsAuth(false);
    setUser(null);
    setViewMode("landing");
  };

  const handleTriggerPipeline = async (productId: string) => {
    setAnalysingId(productId);
    try {
      await api.triggerAnalysis(productId);
      fetchData();
      alert("AI Agents analysis pipeline finished. Check recommendations / audit trail for updates!");
    } catch (err: any) {
      alert(`Pipeline failed: ${err.message}`);
    } finally {
      setAnalysingId(null);
    }
  };

  const handleApprove = async (recId: string) => {
    if (!confirm("Are you sure you want to approve this recommendation price?")) return;
    try {
      await api.approveRecommendation(recId);
      setDrawerOpen(false);
      fetchData();
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    }
  };

  const handleReject = async (recId: string) => {
    if (!rejectionReason) {
      alert("Please provide a reason for rejection.");
      return;
    }
    try {
      await api.rejectRecommendation(recId, rejectionReason);
      setDrawerOpen(false);
      setShowRejectForm(false);
      setRejectionReason("");
      fetchData();
    } catch (err: any) {
      alert(`Rejection failed: ${err.message}`);
    }
  };

  const handleOverride = async (recId: string) => {
    const parsedPrice = parseFloat(overridePrice);
    if (isNaN(parsedPrice) || parsedPrice <= 0) {
      alert("Please specify a valid positive decimal price.");
      return;
    }
    try {
      await api.modifyRecommendation(recId, parsedPrice);
      setDrawerOpen(false);
      setShowOverrideForm(false);
      setOverridePrice("");
      fetchData();
    } catch (err: any) {
      alert(`Override failed: ${err.message}`);
    }
  };

  const handleUpdateConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setConfigSuccess(false);
    try {
      await api.updateConfig({
        auto_execute_threshold: configThreshold,
        category_margin_floors: {
          electronics: electronicsFloor,
          apparel: apparelFloor,
          "home goods": homeGoodsFloor
        }
      });
      setConfigSuccess(true);
      setTimeout(() => setConfigSuccess(false), 3000);
    } catch (err: any) {
      alert(`Failed to update config: ${err.message}`);
    }
  };

  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Convert Rupee inputs back to USD for the API catalog
      await api.createProduct({
        sku,
        name,
        category,
        current_price: parseFloat(currentPrice) / USD_TO_INR,
        cogs: parseFloat(cogs) / USD_TO_INR,
        inventory_count: parseInt(inventoryCount),
        margin_threshold: parseFloat(marginThreshold)
      });
      setShowAddModal(false);
      setSku("");
      setName("");
      setCurrentPrice("");
      setCogs("");
      setInventoryCount("");
      setMarginThreshold("0.15");
      fetchData();
    } catch (err: any) {
      alert(`Failed to add SKU: ${err.message}`);
    }
  };

  const handleEditProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Convert Rupee inputs back to USD for the API catalog
      await api.updateProduct(editingProduct.id, {
        name,
        category,
        current_price: parseFloat(currentPrice) / USD_TO_INR,
        cogs: parseFloat(cogs) / USD_TO_INR,
        inventory_count: parseInt(inventoryCount),
        margin_threshold: parseFloat(marginThreshold)
      });
      setShowEditModal(false);
      setEditingProduct(null);
      setName("");
      setCurrentPrice("");
      setCogs("");
      setInventoryCount("");
      setMarginThreshold("0.15");
      fetchData();
    } catch (err: any) {
      alert(`Failed to update SKU: ${err.message}`);
    }
  };

  const handleDeleteProduct = async (productId: string) => {
    if (!confirm("Are you sure you want to delete this product SKU from the catalog?")) return;
    try {
      await api.deleteProduct(productId);
      fetchData();
    } catch (err: any) {
      alert(`Failed to delete SKU: ${err.message}`);
    }
  };

  const openEditModal = (p: any) => {
    setEditingProduct(p);
    setSku(p.sku);
    setName(p.name);
    setCategory(p.category);
    // Display values in Rupees inside the modal form
    setCurrentPrice((p.current_price * USD_TO_INR).toFixed(2));
    setCogs((p.cogs * USD_TO_INR).toFixed(2));
    setInventoryCount(p.inventory_count.toString());
    setMarginThreshold(p.margin_threshold.toString());
    setShowEditModal(true);
  };

  const openRecDetails = (rec: any) => {
    setSelectedRec(rec);
    setDrawerOpen(true);
  };

  // Stats calculation
  const totalSKUs = products.length;
  const criticallyLowStock = products.filter(p => p.inventory_count <= 10).length;
  const avgMargin = totalSKUs > 0 
    ? (products.reduce((acc, p) => acc + ((parseFloat(p.current_price) - parseFloat(p.cogs)) / parseFloat(p.current_price) * 100), 0) / totalSKUs).toFixed(1)
    : "0.0";

  if (viewMode === "landing") {
    return (
      <div className="landing-container">
        {/* Glow blur background */}
        <div className="landing-glow" />

        {/* Landing Top Navbar */}
        <nav style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "1.5rem 2rem",
          borderBottom: "1px solid var(--border-color)",
          position: "relative",
          zIndex: 100,
          maxWidth: "1200px",
          margin: "0 auto",
          width: "100%"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "1.25rem", fontWeight: 700, color: "var(--text-primary)" }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 22H22L12 2Z" stroke="#8b5cf6" strokeWidth="2" strokeLinejoin="round"/>
            </svg>
            <span style={{
              background: "linear-gradient(135deg, var(--text-primary), var(--accent-primary))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent"
            }}>PRICEMATRIX</span>
          </div>
          <div style={{ display: "flex", gap: "1rem" }}>
            <button className="btn btn-secondary" onClick={() => { setViewMode("app"); setAuthMode("login"); }} style={{ padding: "0.5rem 1.25rem", fontSize: "0.875rem" }}>
              Sign In
            </button>
            <button className="btn btn-primary" onClick={() => { setViewMode("app"); setAuthMode("register"); }} style={{ padding: "0.5rem 1.25rem", fontSize: "0.875rem" }}>
              Sign Up
            </button>
          </div>
        </nav>

        {/* Hero Section */}
        <header className="landing-hero" style={{ padding: "6rem 2rem 5rem 2rem" }}>
          <div className="landing-badge">AI Pricing Engine v1.0 • Llama 3 Enabled</div>
          <h1 className="landing-title">Optimize E-commerce Margins <br />With Collaborative AI Agents</h1>
          <p className="landing-subtitle">
            PriceMatrix AI deploys 5 specialized, autonomous AI agents to dynamically monitor competitor movements, forecast demand signals, and audit stock levels—keeping managers in control with human-in-the-loop safety.
          </p>
          <div className="landing-buttons">
            <button className="btn btn-primary" onClick={() => setViewMode("app")} style={{ fontSize: "1rem", padding: "0.8rem 2rem" }}>
              Launch Console &rarr;
            </button>
            <a href="#features" className="btn btn-secondary" style={{ fontSize: "1rem", padding: "0.8rem 2rem" }}>
              Explore Features
            </a>
          </div>
        </header>

        {/* Purpose / Features Section */}
        <section id="features" className="landing-features" style={{ borderTop: "1px solid var(--border-color)" }}>
          <h2 className="landing-section-title">The Dynamic Pricing Workflow</h2>
          <div className="landing-grid">
            <div className="landing-feat-card">
              <div className="landing-feat-icon">
                <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
              </div>
              <h3>Collaborative Intelligence</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                Autonomous agents cooperate (Market, Demand, Inventory, Strategy, Compliance) using Llama 3 to formulate optimized recommendations.
              </p>
            </div>

            <div className="landing-feat-card">
              <div className="landing-feat-icon">
                <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" /></svg>
              </div>
              <h3>Safety Margin Compliance</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                Compliance guardrails dynamically override suggested pricing if it violates margin floors configured by workspace administrators.
              </p>
            </div>

            <div className="landing-feat-card">
              <div className="landing-feat-icon">
                <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" /></svg>
              </div>
              <h3>HITL Approval Routing</h3>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>
                High-confidence decisions auto-execute immediately to the storefront. Lower confidence suggestions are routed to a manual approval queue with detailed LLM rationale.
              </p>
            </div>
          </div>
        </section>

        {/* Pricing Section with Rupee Equivalents */}
        <section className="landing-pricing" style={{ borderTop: "1px solid var(--border-color)" }}>
          <h2 className="landing-section-title">Transparent Software Pricing</h2>
          <p style={{ textAlign: "center", color: "var(--text-secondary)", marginTop: "-2rem", marginBottom: "3rem", fontSize: "0.95rem" }}>
            Choose the plan that suits your catalog. All plans billed in local currency.
          </p>
          <div className="pricing-grid">
            {/* Starter Plan */}
            <div className="pricing-card">
              <div className="pricing-header">
                <h3>Starter Catalog</h3>
                <p className="pricing-desc">For small boutique e-commerce stores.</p>
              </div>
              <div className="pricing-price">
                ₹4,116<span>/mo</span>
              </div>
              <ul className="pricing-features-list" style={{ marginTop: "1.5rem" }}>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Up to 100 Monitored SKUs</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Daily Competitor Monitoring</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Rule-based pricing constraints</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Standard email support</li>
              </ul>
              <button className="btn btn-secondary w-full" onClick={() => { setViewMode("app"); setAuthMode("register"); }}>
                Get Started
              </button>
            </div>

            {/* Growth / Pro Plan */}
            <div className="pricing-card premium">
              <div className="pricing-header">
                <h3>Scale & Automation</h3>
                <p className="pricing-desc">For growing e-commerce retailers.</p>
              </div>
              <div className="pricing-price">
                ₹12,516<span>/mo</span>
              </div>
              <ul className="pricing-features-list" style={{ marginTop: "1.5rem" }}>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Up to 1,000 Monitored SKUs</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Real-time AI Multi-Agent analysis</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Auto-execution configurations</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Priority 24/7 Support</li>
              </ul>
              <button className="btn btn-primary w-full" onClick={() => { setViewMode("app"); setAuthMode("register"); }}>
                Start Free Trial
              </button>
            </div>

            {/* Enterprise Plan */}
            <div className="pricing-card">
              <div className="pricing-header">
                <h3>Enterprise Suite</h3>
                <p className="pricing-desc">For high-volume brands needing custom rules.</p>
              </div>
              <div className="pricing-price">
                ₹41,916<span>/mo</span>
              </div>
              <ul className="pricing-features-list" style={{ marginTop: "1.5rem" }}>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Unlimited SKUs</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Custom dedicated AI Agent nodes</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Dedicated account manager</li>
                <li><svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" style={{ marginRight: "0.25rem" }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" /></svg>Custom storefront integrations</li>
              </ul>
              <button className="btn btn-secondary w-full" onClick={() => setViewMode("app")}>
                Contact Sales
              </button>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer style={{ borderTop: "1px solid var(--border-color)", padding: "2.5rem 2rem", textAlign: "center", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
          &copy; 2026 PriceMatrix AI Inc. All rights reserved. Built with NextJS and FastAPI.
        </footer>
      </div>
    );
  }

  if (!isAuth) {
    return (
      <div className="auth-page">
        <div style={{ position: "absolute", top: "1.5rem", left: "1.5rem" }}>
          <button className="btn btn-secondary" onClick={() => setViewMode("landing")} style={{ fontSize: "0.875rem", padding: "0.5rem 1rem" }}>
            &larr; Back to Landing Page
          </button>
        </div>
        <div className="auth-card">
          <h2 className="mb-2" style={{ textAlign: "center", color: "#8b5cf6" }}>PRICEMATRIX AI</h2>
          <p className="mb-3" style={{ textAlign: "center", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
            {authMode === "login" ? "Sign in to access catalog recommendations" : "Create new organization workspace"}
          </p>

          <form onSubmit={handleAuthSubmit}>
            {authMode === "register" && (
              <div className="form-group">
                <label>Full Name</label>
                <input type="text" value={fullName} onChange={e => setFullName(e.target.value)} required placeholder="John Doe" />
              </div>
            )}

            <div className="form-group">
              <label>Email Address</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="admin@klypup.com" />
            </div>

            <div className="form-group">
              <label>Password</label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)} required placeholder="••••••••" />
            </div>

            {authMode === "register" && (
              <>
                <div className="form-group">
                  <label>Pricing Role</label>
                  <select value={role} onChange={e => setRole(e.target.value)}>
                    <option value="ADMIN">Workspace Admin</option>
                    <option value="ANALYST">Pricing Analyst</option>
                  </select>
                </div>

                <div className="form-group">
                  <label>Create New Organization Name</label>
                  <input type="text" value={orgName} onChange={e => setOrgName(e.target.value)} placeholder="e.g. Klypup Retail" />
                </div>

                <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.75rem" }} className="mb-2">
                  - OR JOIN EXISTING -
                </div>

                <div className="form-group">
                  <label>Existing Organization ID</label>
                  <input type="text" value={orgIdInput} onChange={e => setOrgIdInput(e.target.value)} placeholder="Paste org UUID" />
                </div>
              </>
            )}

            {authError && (
              <div className="badge badge-danger mb-2 w-full" style={{ justifyContent: "center" }}>
                {authError}
              </div>
            )}

            <button type="submit" className="btn btn-primary w-full mt-2">
              {authMode === "login" ? "Sign In" : "Register Workspace"}
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: "1.5rem" }}>
            <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>
              {authMode === "login" ? "Don't have a workspace? " : "Already registered? "}
            </span>
            <button
              onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}
              style={{ background: "none", border: "none", color: "#8b5cf6", fontWeight: "bold", cursor: "pointer" }}
            >
              {authMode === "login" ? "Sign Up" : "Log In"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo-section">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L2 22H22L12 2Z" stroke="#8b5cf6" strokeWidth="2" strokeLinejoin="round"/>
          </svg>
          <span>PRICEMATRIX</span>
        </div>

        <nav className="nav-links">
          <div className={`nav-item ${activeTab === "catalog" ? "active" : ""}`} onClick={() => setActiveTab("catalog")}>
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" /></svg>
            SKU Catalog
          </div>
          <div className={`nav-item ${activeTab === "recommendations" ? "active" : ""}`} onClick={() => setActiveTab("recommendations")}>
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            Pending Queue
          </div>
          <div className={`nav-item ${activeTab === "audits" ? "active" : ""}`} onClick={() => setActiveTab("audits")}>
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
            Audit Trail
          </div>
          <div className={`nav-item ${activeTab === "config" ? "active" : ""}`} onClick={() => setActiveTab("config")}>
            <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" /></svg>
            Config Settings
          </div>
        </nav>

        <div style={{ marginTop: "auto" }}>
          <div style={{ fontSize: "0.875rem", marginBottom: "0.75rem", borderTop: "1px solid var(--border-color)", paddingTop: "0.75rem" }}>
            <div style={{ fontWeight: 600 }}>{user?.full_name}</div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>{user?.role}</div>
            <div style={{ color: "var(--text-muted)", fontSize: "0.7rem", wordBreak: "break-all" }}>Org: {user?.org_id}</div>
          </div>
          <button className="btn btn-secondary w-full" onClick={handleLogout}>Logout</button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <header className="header-row">
          <div>
            <h1>{activeTab === "catalog" && "SKU Pricing Catalog"}
                {activeTab === "recommendations" && "AI Recommendations Approval Queue"}
                {activeTab === "audits" && "Pricing Decision Audit Trail"}
                {activeTab === "config" && "Pricing Configurations"}</h1>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>Real-time workspace automation and margins safety</p>
          </div>
          <div className="flex-row">
            {user?.role === "ADMIN" && (
              <button className="btn btn-primary" onClick={() => setShowAddModal(true)}>+ Add SKU</button>
            )}
            <button className="btn btn-secondary" onClick={fetchData}>Refresh Data</button>
          </div>
        </header>

        {activeTab === "catalog" && (
          <>
            {/* Stats Cards */}
            <div className="grid-stats">
              <div className="card">
                <div className="card-title">Total Monitored SKUs</div>
                <div className="card-value">{totalSKUs}</div>
                <div className="card-subtext">Dynamic pricing enabled</div>
              </div>
              <div className="card">
                <div className="card-title">Critically Low Stock</div>
                <div className="card-value" style={{ color: criticallyLowStock > 0 ? "var(--status-danger)" : "var(--text-primary)" }}>
                  {criticallyLowStock}
                </div>
                <div className="card-subtext">Risk of stockouts</div>
              </div>
              <div className="card">
                <div className="card-title">Average Profit Margin</div>
                <div className="card-value" style={{ color: "var(--status-success)" }}>{avgMargin}%</div>
                <div className="card-subtext">Category margins compliance</div>
              </div>
            </div>

            {/* Filter controls */}
            <div className="card mb-3 flex-row justify-between" style={{ flexWrap: "wrap", gap: "1rem" }}>
              <div className="flex-row" style={{ flexWrap: "wrap", gap: "1rem" }}>
                <input
                  type="text"
                  placeholder="Search SKU or name..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  style={{ width: "250px" }}
                />

                <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)}>
                  <option value="">All Categories</option>
                  <option value="electronics">Electronics</option>
                  <option value="apparel">Apparel</option>
                  <option value="home goods">Home Goods</option>
                </select>

                <select value={stockFilter} onChange={e => setStockFilter(e.target.value)}>
                  <option value="">All Stock Levels</option>
                  <option value="critically_low">Critically Low (&lt;= 10)</option>
                  <option value="healthy">Healthy (11-100)</option>
                  <option value="overstocked">Overstocked (&gt; 100)</option>
                </select>
              </div>

              <div className="flex-row">
                <span style={{ fontSize: "0.875rem", color: "var(--text-secondary)" }}>Sort by:</span>
                <select value={sortBy} onChange={e => setSortBy(e.target.value)}>
                  <option value="sku">SKU Code</option>
                  <option value="current_price">Price</option>
                  <option value="inventory_count">Inventory</option>
                </select>
                <select value={sortOrder} onChange={e => setSortOrder(e.target.value)}>
                  <option value="asc">Ascending</option>
                  <option value="desc">Descending</option>
                </select>
              </div>
            </div>

            {/* Catalog Table */}
            <div className="table-container">
              {loading ? (
                <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>Loading SKU catalog...</div>
              ) : products.length === 0 ? (
                <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>No products found matching filters.</div>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>SKU</th>
                      <th>Product Name</th>
                      <th>Category</th>
                      <th>Stock Level</th>
                      <th>COGS</th>
                      <th>Current Price</th>
                      <th>Margin (%)</th>
                      <th style={{ textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {products.map(p => {
                      const margin = (((p.current_price - p.cogs) / p.current_price) * 100).toFixed(1);
                      return (
                        <tr key={p.id}>
                          <td style={{ fontWeight: 600 }}>{p.sku}</td>
                          <td>{p.name}</td>
                          <td style={{ textTransform: "capitalize" }}>{p.category}</td>
                          <td>
                            <span className={`badge ${p.inventory_count <= 10 ? "badge-danger" : p.inventory_count >= 100 ? "badge-warning" : "badge-success"}`}>
                              {p.inventory_count} units
                            </span>
                          </td>
                          <td>{formatCurrency(p.cogs)}</td>
                          <td style={{ fontWeight: 600 }}>{formatCurrency(p.current_price)}</td>
                          <td style={{ color: parseFloat(margin) < p.margin_threshold * 100 ? "var(--status-danger)" : "var(--status-success)" }}>
                            {margin}%
                          </td>
                          <td style={{ textAlign: "right" }}>
                            <div style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                              <button
                                className="btn btn-primary"
                                style={{ padding: "0.4rem 0.8rem", fontSize: "0.75rem" }}
                                onClick={() => handleTriggerPipeline(p.id)}
                                disabled={analysingId === p.id}
                              >
                                {analysingId === p.id ? "Analysing..." : "Run AI Agents"}
                              </button>
                              {user?.role === "ADMIN" && (
                                <>
                                  <button
                                    className="btn btn-secondary"
                                    style={{ padding: "0.4rem 0.6rem", fontSize: "0.75rem" }}
                                    onClick={() => openEditModal(p)}
                                  >
                                    Edit
                                  </button>
                                  <button
                                    className="btn btn-danger"
                                    style={{ padding: "0.4rem 0.6rem", fontSize: "0.75rem" }}
                                    onClick={() => handleDeleteProduct(p.id)}
                                  >
                                    Delete
                                  </button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}

        {activeTab === "recommendations" && (
          <div className="table-container">
            {loading ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>Loading queue...</div>
            ) : recommendations.length === 0 ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>No pending recommendations. Run AI Agents on SKUs!</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Suggested SKU</th>
                    <th>Recommended Price</th>
                    <th>Confidence</th>
                    <th>Suggested At</th>
                    <th style={{ textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {recommendations.map(r => (
                    <tr key={r.id}>
                      <td style={{ fontWeight: 600 }}>{r.agent_rationale.market?.sku || "SKU"}</td>
                      <td style={{ fontWeight: 600, color: "var(--accent-primary)" }}>{formatCurrency(r.recommended_price)}</td>
                      <td>
                        <span className={`badge ${r.confidence_score >= 0.8 ? "badge-success" : "badge-warning"}`}>
                          {Math.round(r.confidence_score * 100)}% Confidence
                        </span>
                      </td>
                      <td>{new Date(r.suggested_at).toLocaleString()}</td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="btn btn-secondary"
                          style={{ padding: "0.4rem 0.8rem", fontSize: "0.75rem" }}
                          onClick={() => openRecDetails(r)}
                        >
                          Review Agents Rationale &rarr;
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === "audits" && (
          <div className="table-container">
            {loading ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>Loading audits...</div>
            ) : audits.length === 0 ? (
              <div style={{ padding: "3rem", textAlign: "center", color: "var(--text-secondary)" }}>No audits recorded yet. Approve recommendations to see records.</div>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Product Name</th>
                    <th>Product ID</th>
                    <th>SKU</th>
                    <th>Old Price</th>
                    <th>New Price</th>
                    <th>Type</th>
                    <th>Authorized By</th>
                  </tr>
                </thead>
                <tbody>
                  {audits.map(a => (
                    <tr key={a.id}>
                      <td>{new Date(a.changed_at).toLocaleString()}</td>
                      <td style={{ fontWeight: 500 }}>{a.product_name || "N/A"}</td>
                      <td style={{ fontSize: "0.8rem", color: "var(--text-secondary)", fontFamily: "monospace" }}>{a.product_id}</td>
                      <td style={{ fontWeight: 600 }}>{a.product_sku || "N/A"}</td>
                      <td>{formatCurrency(a.old_price)}</td>
                      <td style={{ color: parseFloat(a.new_price) > parseFloat(a.old_price) ? "var(--status-success)" : "var(--status-danger)", fontWeight: 600 }}>
                        {formatCurrency(a.new_price)}
                      </td>
                      <td>
                        <span className={`badge ${a.change_type === "AUTO" ? "badge-info" : a.change_type === "APPROVED" ? "badge-success" : "badge-warning"}`}>
                          {a.change_type}
                        </span>
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>{a.changed_by}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {activeTab === "config" && (
          <div className="card w-full" style={{ maxWidth: "700px" }}>
            <h2 className="mb-2">Admin Configuration Thresholds</h2>
            <p className="mb-3" style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
              Define pricing boundaries and auto-execution limits
            </p>

            <form onSubmit={handleUpdateConfig}>
              <div className="form-group mb-3">
                <label className="flex-row justify-between">
                  <span>Auto-Execution Confidence Threshold</span>
                  <span style={{ color: "var(--accent-primary)", fontWeight: "bold" }}>{Math.round(configThreshold * 100)}%</span>
                </label>
                <input
                  type="range"
                  min="0.50"
                  max="0.95"
                  step="0.05"
                  value={configThreshold}
                  onChange={e => setConfigThreshold(parseFloat(e.target.value))}
                  disabled={user?.role !== "ADMIN"}
                />
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  Recommendations above this confidence level will immediately update your storefront price without requiring manual verification.
                </span>
              </div>

              <h3 className="mb-2 mt-3" style={{ fontSize: "1rem" }}>Minimum Margin Floors (%)</h3>

              <div className="form-group">
                <label>Electronics Margin Floor</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="0.9"
                  value={electronicsFloor}
                  onChange={e => setElectronicsFloor(parseFloat(e.target.value))}
                  disabled={user?.role !== "ADMIN"}
                />
              </div>

              <div className="form-group">
                <label>Apparel Margin Floor</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="0.9"
                  value={apparelFloor}
                  onChange={e => setApparelFloor(parseFloat(e.target.value))}
                  disabled={user?.role !== "ADMIN"}
                />
              </div>

              <div className="form-group">
                <label>Home Goods Margin Floor</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="0.9"
                  value={homeGoodsFloor}
                  onChange={e => setHomeGoodsFloor(parseFloat(e.target.value))}
                  disabled={user?.role !== "ADMIN"}
                />
              </div>

              {configSuccess && (
                <div className="badge badge-success mb-2 w-full" style={{ justifyContent: "center" }}>
                  Configurations updated successfully!
                </div>
              )}

              {user?.role === "ADMIN" ? (
                <button type="submit" className="btn btn-primary w-full mt-2">
                  Save Configurations
                </button>
              ) : (
                <div className="badge badge-warning w-full mt-2" style={{ justifyContent: "center" }}>
                  Only Workspace Admins can edit configuration settings.
                </div>
              )}
            </form>
          </div>
        )}
      </main>

      {/* Add SKU Modal (Admin Only) */}
      {showAddModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
          backgroundColor: "rgba(0,0,0,0.7)", zIndex: 200, display: "flex",
          justifyContent: "center", alignItems: "center", backdropFilter: "blur(4px)"
        }}>
          <div className="card" style={{ width: "450px", padding: "2rem" }}>
            <h2 className="mb-2">Add Product SKU</h2>
            <form onSubmit={handleAddProduct}>
              <div className="form-group">
                <label>SKU Code</label>
                <input type="text" value={sku} onChange={e => setSku(e.target.value)} required placeholder="e.g. ELE-SONY-XM5" />
              </div>
              <div className="form-group">
                <label>Product Name</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} required placeholder="e.g. Sony Headset" />
              </div>
              <div className="form-group">
                <label>Category</label>
                <select value={category} onChange={e => setCategory(e.target.value)}>
                  <option value="electronics">Electronics</option>
                  <option value="apparel">Apparel</option>
                  <option value="home goods">Home Goods</option>
                </select>
              </div>
              <div className="form-group">
                <label>Current Price (INR - ₹)</label>
                <input type="number" step="0.01" value={currentPrice} onChange={e => setCurrentPrice(e.target.value)} required placeholder="25199.16" />
              </div>
              <div className="form-group">
                <label>COGS (INR - ₹)</label>
                <input type="number" step="0.01" value={cogs} onChange={e => setCogs(e.target.value)} required placeholder="16800.00" />
              </div>
              <div className="form-group">
                <label>Inventory Count</label>
                <input type="number" value={inventoryCount} onChange={e => setInventoryCount(e.target.value)} required placeholder="50" />
              </div>
              <div className="form-group">
                <label>Min Margin Threshold (as decimal)</label>
                <input type="number" step="0.01" value={marginThreshold} onChange={e => setMarginThreshold(e.target.value)} required placeholder="0.15" />
              </div>
              <div className="flex-row gap-2 mt-2">
                <button type="submit" className="btn btn-primary" style={{ flexGrow: 1 }}>Save SKU</button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit SKU Modal (Admin Only) */}
      {showEditModal && (
        <div style={{
          position: "fixed", top: 0, left: 0, width: "100vw", height: "100vh",
          backgroundColor: "rgba(0,0,0,0.7)", zIndex: 200, display: "flex",
          justifyContent: "center", alignItems: "center", backdropFilter: "blur(4px)"
        }}>
          <div className="card" style={{ width: "450px", padding: "2rem" }}>
            <h2 className="mb-2">Edit Product SKU ({sku})</h2>
            <form onSubmit={handleEditProduct}>
              <div className="form-group">
                <label>Product Name</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Category</label>
                <select value={category} onChange={e => setCategory(e.target.value)}>
                  <option value="electronics">Electronics</option>
                  <option value="apparel">Apparel</option>
                  <option value="home goods">Home Goods</option>
                </select>
              </div>
              <div className="form-group">
                <label>Current Price (INR - ₹)</label>
                <input type="number" step="0.01" value={currentPrice} onChange={e => setCurrentPrice(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>COGS (INR - ₹)</label>
                <input type="number" step="0.01" value={cogs} onChange={e => setCogs(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Inventory Count</label>
                <input type="number" value={inventoryCount} onChange={e => setInventoryCount(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Min Margin Threshold (as decimal)</label>
                <input type="number" step="0.01" value={marginThreshold} onChange={e => setMarginThreshold(e.target.value)} required />
              </div>
              <div className="flex-row gap-2 mt-2">
                <button type="submit" className="btn btn-primary" style={{ flexGrow: 1 }}>Save Changes</button>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowEditModal(false); setEditingProduct(null); }}>Cancel</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Slide-out Drawer Panel (Reviewing AI Rationale) */}
      <div className={`drawer-overlay ${drawerOpen ? "open" : ""}`} onClick={() => setDrawerOpen(false)} />
      <div className={`drawer ${drawerOpen ? "open" : ""}`}>
        {selectedRec && (
          <>
            <div className="flex-row justify-between mb-3" style={{ borderBottom: "1px solid var(--border-color)", paddingBottom: "1rem" }}>
              <h2>Review Pricing Rationale</h2>
              <button
                onClick={() => setDrawerOpen(false)}
                style={{ background: "none", border: "none", color: "var(--text-muted)", fontSize: "1.5rem", cursor: "pointer" }}
              >
                &times;
              </button>
            </div>

            <div className="mb-3">
              <h3 style={{ fontSize: "1.1rem" }} className="mb-1">Proposed Price: {formatCurrency(selectedRec.recommended_price)}</h3>
              <div className="flex-row gap-2">
                <span className={`badge ${selectedRec.confidence_score >= 0.85 ? "badge-success" : "badge-warning"}`}>
                  {Math.round(selectedRec.confidence_score * 100)}% Confidence
                </span>
                <span className="badge badge-info">
                  SKU: {selectedRec.agent_rationale.market?.sku}
                </span>
              </div>
            </div>

            {/* Custom SVG Line Chart */}
            <div className="mb-3">
              <h4 style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase" }}>Price delta timeline</h4>
              <svg className="chart-svg">
                {/* Grid Lines */}
                <line x1="10%" y1="20%" x2="90%" y2="20%" className="chart-grid" />
                <line x1="10%" y1="50%" x2="90%" y2="50%" className="chart-grid" />
                <line x1="10%" y1="80%" x2="90%" y2="80%" className="chart-grid" />
                
                {/* Labels */}
                <text x="5%" y="23%" fill="var(--text-muted)" fontSize="10">High</text>
                <text x="5%" y="53%" fill="var(--text-muted)" fontSize="10">Mid</text>
                <text x="5%" y="83%" fill="var(--text-muted)" fontSize="10">Low</text>
                
                {/* Lines */}
                <path d="M 50 150 L 150 120 L 250 80 L 350 110 L 450 60" className="chart-line-our" />
                <path d="M 50 160 L 150 140 L 250 100 L 350 90 L 450 80" className="chart-line-comp" />
                
                {/* Legend */}
                <rect x="50" y="10" width="10" height="10" fill="var(--accent-primary)" />
                <text x="65" y="19" fill="var(--text-secondary)" fontSize="10">Our Proposal</text>
                <rect x="180" y="10" width="10" height="10" fill="var(--status-warning)" />
                <text x="195" y="19" fill="var(--text-secondary)" fontSize="10">Competitor Avg</text>
              </svg>
            </div>

            {/* Strategy Synthesis Rationale */}
            <div className="card mb-3" style={{ borderColor: "var(--accent-primary)" }}>
              <div className="card-title" style={{ color: "var(--accent-primary)" }}>Pricing Strategy Orchestration</div>
              <p style={{ fontSize: "0.9rem" }}>{selectedRec.agent_rationale.strategy_rationale}</p>
            </div>

            {/* Agent Contributions Accordion */}
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }} className="mb-3">
              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ fontWeight: 600, display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                  <span>Market Intelligence Agent</span>
                  <span className={`badge ${selectedRec.agent_rationale.market?.overall_sentiment === "NEGATIVE" ? "badge-danger" : "badge-success"}`}>
                    {selectedRec.agent_rationale.market?.overall_sentiment} SENTIMENT
                  </span>
                </div>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  {selectedRec.agent_rationale.market?.market_rationale}
                </p>
                <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Competitor Average: {formatCurrency(selectedRec.agent_rationale.market?.average_competitor_price)}
                </div>
              </div>

              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ fontWeight: 600, display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                  <span>Demand Forecasting Agent</span>
                  <span className="badge badge-info">
                    {selectedRec.agent_rationale.demand?.demand_intensity} DEMAND
                  </span>
                </div>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  {selectedRec.agent_rationale.demand?.demand_rationale}
                </p>
                <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Sales Velocity: {selectedRec.agent_rationale.demand?.sales_velocity_30d} units/30d | Elasticity: {selectedRec.agent_rationale.demand?.projected_elasticity}
                </div>
              </div>

              <div className="card" style={{ padding: "1rem" }}>
                <div style={{ fontWeight: 600, display: "flex", justifyContent: "space-between", marginBottom: "0.3rem" }}>
                  <span>Inventory & Cost Agent</span>
                  <span className={`badge ${selectedRec.agent_rationale.inventory?.stock_status === "CRITICALLY_LOW" ? "badge-danger" : "badge-success"}`}>
                    {selectedRec.agent_rationale.inventory?.stock_status}
                  </span>
                </div>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                  {selectedRec.agent_rationale.inventory?.inventory_rationale}
                </p>
                <div style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Current Stock: {selectedRec.agent_rationale.inventory?.current_stock} units | Margin Floor Price: {formatCurrency(selectedRec.agent_rationale.inventory?.margin_floor_price)}
                </div>
              </div>
            </div>

            {/* Action buttons */}
            <div style={{ borderTop: "1px solid var(--border-color)", paddingTop: "1.5rem" }}>
              {!showRejectForm && !showOverrideForm && (
                <div style={{ display: "flex", gap: "1rem" }}>
                  <button className="btn btn-success" style={{ flexGrow: 1 }} onClick={() => handleApprove(selectedRec.id)}>
                    Approve Recommendation
                  </button>
                  <button className="btn btn-danger" onClick={() => setShowRejectForm(true)}>
                    Reject
                  </button>
                  <button className="btn btn-secondary" onClick={() => setShowOverrideForm(true)}>
                    Modify Price
                  </button>
                </div>
              )}

              {showRejectForm && (
                <div className="form-group card">
                  <label>Reason for Rejection</label>
                  <input
                    type="text"
                    value={rejectionReason}
                    onChange={e => setRejectionReason(e.target.value)}
                    placeholder="Provide a reason..."
                  />
                  <div className="flex-row gap-2 mt-2">
                    <button className="btn btn-danger" style={{ flexGrow: 1 }} onClick={() => handleReject(selectedRec.id)}>
                      Confirm Rejection
                    </button>
                    <button className="btn btn-secondary" onClick={() => { setShowRejectForm(false); setRejectionReason(""); }}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {showOverrideForm && (
                <div className="form-group card">
                  <label>Override Recommended Price</label>
                  <input
                    type="number"
                    step="0.01"
                    value={overridePrice}
                    onChange={e => setOverridePrice(e.target.value)}
                    placeholder={`Floor is ${formatCurrency(selectedRec.agent_rationale.inventory?.margin_floor_price)}`}
                  />
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }} className="mb-1">
                    Manual overrides must be higher than the margin floor of {formatCurrency(selectedRec.agent_rationale.inventory?.margin_floor_price)}
                  </span>
                  <div className="flex-row gap-2 mt-2">
                    <button className="btn btn-primary" style={{ flexGrow: 1 }} onClick={() => handleOverride(selectedRec.id)}>
                      Sync Override Price
                    </button>
                    <button className="btn btn-secondary" onClick={() => { setShowOverrideForm(false); setOverridePrice(""); }}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
