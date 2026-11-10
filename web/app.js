/* ==========================================================
   GameMaster AI · 前端应用
   ----------------------------------------------------------
   - 原生 JS，无构建步骤，由 FastAPI 静态托管
   - 所有数据来自 /api，多租户通过 X-Tenant 头传递
   - UI 文案全部中文；知识内容与模型输出均做 HTML 转义
   ========================================================== */

(function () {
  "use strict";

  const TENANT_KEY = "gm_tenant";
  const TRAINEE_KEY = "gm_trainee";
  const RUN_KEY = "gm_run";
  const DEFAULT_TENANT = "starsea";
  const MAX_HINTS = 5;
  const PASS_LINE = 80;
  const RING_LEN = 339.292;

  let TENANT = DEFAULT_TENANT;
  try {
    TENANT = localStorage.getItem(TENANT_KEY) || DEFAULT_TENANT;
  } catch (e) {
    /* 忽略隐私模式下的存储异常 */
  }

  const S = {
    meta: null,
    health: null,
    trainees: [],
    traineeId: null,
    progress: null,
    run: null,
    view: "lobby",
    busy: false,
    admin: null,
    adminLoading: false,
    clockTimer: null,
    lastPlayerAt: null,
    lastTurn: null,
    lastHint: null,
    confirmCb: null,
    roi: null,
    draft: "",
    booted: false,
  };

  /* ---------------- 基础工具 ---------------- */

  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.prototype.slice.call((root || document).querySelectorAll(sel));

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  const store = {
    get(key) {
      try {
        return localStorage.getItem(key);
      } catch (e) {
        return null;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, value);
      } catch (e) {
        /* 忽略 */
      }
    },
    del(key) {
      try {
        localStorage.removeItem(key);
      } catch (e) {
        /* 忽略 */
      }
    },
  };

  function fmtInt(n) {
    return Math.round(Number(n) || 0).toLocaleString("zh-CN");
  }

  function fmtCompact(n) {
    const v = Math.round(Number(n) || 0);
    if (v >= 10000) {
      const w = v / 10000;
      const txt = w >= 100 ? w.toFixed(0) : w.toFixed(1);
      return txt.replace(/\.0$/, "") + " 万";
    }
    return fmtInt(v);
  }

  function fmtOne(n) {
    const v = Number(n);
    if (!Number.isFinite(v)) return "—";
    return v.toFixed(1);
  }

  function fmtPct(ratio) {
    return Math.round((Number(ratio) || 0) * 100) + "%";
  }

  function fmtTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    try {
      return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
    } catch (e) {
      return "";
    }
  }

  function fmtDateTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "—";
    const pad = (n) => String(n).padStart(2, "0");
    return (
      d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes())
    );
  }

  function fmtShortDateTime(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "—";
    const pad = (n) => String(n).padStart(2, "0");
    return pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + " " + pad(d.getHours()) + ":" + pad(d.getMinutes());
  }

  function relTime(iso) {
    if (!iso) return "";
    const t = Date.parse(iso);
    if (!t) return "";
    const diff = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (diff < 60) return "刚刚";
    if (diff < 3600) return Math.floor(diff / 60) + " 分钟前";
    if (diff < 86400) return Math.floor(diff / 3600) + " 小时前";
    if (diff < 86400 * 30) return Math.floor(diff / 86400) + " 天前";
    return fmtShortDateTime(iso);
  }

  function formatDuration(sec) {
    const s = Math.max(0, Math.round(Number(sec) || 0));
    const m = Math.floor(s / 60);
    return m + " 分 " + (s % 60) + " 秒";
  }

  function latencyText(ms) {
    if (ms == null) return "";
    const s = Number(ms) / 1000;
    if (!Number.isFinite(s)) return "";
    return (s < 10 ? s.toFixed(1) : Math.round(s)) + "s";
  }

  function latencyColor(ms) {
    if (ms == null) return "";
    const s = Number(ms) / 1000;
    if (s <= 15) return "var(--green)";
    if (s <= 40) return "var(--amber)";
    return "var(--red)";
  }

  function barColor(score) {
    if (score >= 85) return "var(--green)";
    if (score >= 70) return "var(--cyan)";
    if (score >= 50) return "var(--amber)";
    return "var(--red)";
  }

  function gradeColor(grade) {
    return { S: "#ffc857", A: "#3fe0a7", B: "#37e1ff", C: "#ffab5c", D: "#ff6b81" }[grade] || "#37e1ff";
  }

  function emotionMeta(value) {
    const v = Math.max(1, Math.min(10, Number(value) || 5));
    if (v <= 3) {
      return { label: "平静", face: "😌", color: "#3fe0a7", note: "玩家情绪平稳，可以直接进入问题处理，并把闭环动作说清楚。" };
    }
    if (v <= 5) {
      return { label: "观望", face: "😐", color: "#ffc857", note: "玩家在观察你的态度：先确认诉求，再给步骤，避免一上来念规则。" };
    }
    if (v <= 7) {
      return { label: "不满", face: "😠", color: "#ffab5c", note: "情绪偏高：先承接感受，再处理问题。模板化回复会继续激怒玩家。" };
    }
    if (v <= 8) {
      return { label: "愤怒", face: "😡", color: "#ff8a5c", note: "明显愤怒：正面承认体验影响，给出实质动作和明确时间点。" };
    }
    return { label: "爆发边缘", face: "🤬", color: "#ff6b81", note: "已到爆发边缘：先稳住情绪，承认问题并说明你会怎么跟进。" };
  }

  function formatClock(secs) {
    const s = Math.max(0, Math.floor(secs));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const r = s % 60;
    const pad = (n) => String(n).padStart(2, "0");
    return h > 0 ? h + ":" + pad(m) + ":" + pad(r) : pad(m) + ":" + pad(r);
  }

  function stripPunct(s) {
    return String(s || "").replace(/[\s·:：]+/g, "");
  }

  /* ---------------- API ---------------- */

  async function api(path, opts) {
    const options = opts || {};
    const method = options.method || "GET";
    const headers = {};
    if (options.tenant !== false) headers["X-Tenant"] = TENANT;
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    let res;
    try {
      res = await fetch("/api" + path, {
        method: method,
        headers: headers,
        body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      });
    } catch (err) {
      throw new Error("无法连接后端服务，请确认 ./run.sh 已启动");
    }
    if (!res.ok) {
      let detail = "";
      try {
        const data = await res.json();
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
      } catch (e) {
        detail = "HTTP " + res.status;
      }
      throw new Error(detail || "请求失败（" + res.status + "）");
    }
    return res.json();
  }

  /* ---------------- 提示与加载 ---------------- */

  function toast(message, type) {
    const root = $("#toast-root");
    if (!root) return;
    const el = document.createElement("div");
    el.className = "toast " + (type || "info");
    const icons = { success: "✓", error: "✕", warn: "!", info: "◆" };
    el.innerHTML = '<span class="ico">' + (icons[type] || "◆") + "</span><span>" + esc(message) + "</span>";
    root.appendChild(el);
    setTimeout(function () {
      el.classList.add("out");
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, 260);
    }, type === "error" || type === "warn" ? 4200 : 3000);
  }

  function showLoading(text) {
    const overlay = $("#loading-overlay");
    if (!overlay) return;
    $("#loading-text").textContent = text || "正在处理…";
    overlay.classList.remove("hidden");
    overlay.removeAttribute("hidden");
  }

  function hideLoading() {
    const overlay = $("#loading-overlay");
    if (!overlay) return;
    overlay.classList.add("hidden");
  }

  /* ---------------- 模态框 ---------------- */

  function openModal(html, opts) {
    const options = opts || {};
    const root = $("#modal-root");
    root.innerHTML =
      '<div class="modal-overlay"><div class="modal-card' + (options.wide ? " wide" : "") +
      '" role="dialog" aria-modal="true">' + html + "</div></div>";
    const input = $("#new-trainee-name");
    if (input) setTimeout(function () { input.focus(); }, 120);
  }

  function closeModal() {
    const root = $("#modal-root");
    if (root) root.innerHTML = "";
    S.confirmCb = null;
  }

  function openConfirm(opts) {
    S.confirmCb = opts.onConfirm || null;
    const tone = opts.tone === "danger" ? "btn gold" : "btn primary";
    openModal(
      '<button class="modal-close" data-act="close-modal" aria-label="关闭">✕</button>' +
        '<div class="modal-head"><p class="eyebrow">CONFIRM</p><h2>' + esc(opts.title || "确认操作") + "</h2>" +
        (opts.body ? "<p>" + esc(opts.body) + "</p>" : "") +
        "</div>" +
        '<div class="modal-actions"><button class="btn ghost" data-act="close-modal">' + esc(opts.cancelText || "取消") +
        '</button><button class="' + tone + '" data-act="confirm-yes">' + esc(opts.confirmText || "确认") + "</button></div>"
    );
  }

  /* ---------------- 启动 ---------------- */

  async function boot() {
    if (S.booted) return;
    S.booted = true;
    bindEvents();
    renderLlm(null);

    let health = null;
    try {
      health = await api("/health", { tenant: false });
      S.health = health;
      renderLlm(health.llm);
    } catch (err) {
      renderLlm(null, true);
    }

    try {
      S.meta = await api("/meta");
    } catch (err) {
      try {
        TENANT = DEFAULT_TENANT;
        S.meta = await api("/meta");
      } catch (err2) {
        renderFatal(err2);
        return;
      }
    }
    if (S.meta && S.meta.tenant && S.meta.tenant.id) {
      TENANT = S.meta.tenant.id;
      store.set(TENANT_KEY, TENANT);
    }
    if (S.meta && S.meta.llm) renderLlm(S.meta.llm);

    await loadTrainees();
    renderTopbar();

    if (!S.trainees.length) {
      renderLobby();
      setView("lobby");
      setTimeout(openNewTraineeModal, 350);
      toast("当前租户还没有学员，先创建一份训练档案", "info");
      return;
    }

    const savedTrainee = store.get(TRAINEE_KEY);
    const initial = S.trainees.some((t) => t.id === savedTrainee) ? savedTrainee : S.trainees[0].id;
    await selectTrainee(initial, { silent: true });

    const restored = await restoreActiveRun();
    setView(restored ? "battle" : "lobby");
    if (restored) toast("已恢复未结束的对练", "info");
  }

  function renderFatal(err) {
    $("#lobby-hero").innerHTML =
      '<div class="panel profile-card" style="grid-column:1/-1;padding:44px 30px">' +
      '<p class="eyebrow">CONNECTION ERROR</p><h1 style="margin-top:8px">无法连接后端服务</h1>' +
      '<p class="muted" style="margin-top:10px">请在项目目录运行 <code>./run.sh</code>，确认服务启动后再刷新本页。</p>' +
      '<p class="muted" style="margin-top:6px;font-family:var(--mono);font-size:11px">' + esc(err && err.message) + "</p></div>";
    $("#badge-strip").innerHTML = "";
    $("#level-map").innerHTML = "";
    $("#recent-runs").innerHTML = "";
    setView("lobby");
  }

  async function loadTrainees() {
    try {
      const data = await api("/trainees");
      S.trainees = data.trainees || [];
    } catch (err) {
      S.trainees = [];
      toast(err.message, "error");
    }
  }

  async function selectTrainee(id, opts) {
    const options = opts || {};
    if (!id || !S.trainees.length) {
      S.traineeId = null;
      S.progress = null;
      renderTopbar();
      return;
    }
    const exists = S.trainees.some((t) => t.id === id);
    if (!exists) id = S.trainees[0].id;
    S.traineeId = id;
    store.set(TRAINEE_KEY, id);
    try {
      S.progress = await api("/trainees/" + encodeURIComponent(id) + "/progress");
    } catch (err) {
      S.progress = null;
      if (!options.silent) toast("加载学员进度失败：" + err.message, "error");
    }
    renderTopbar();
    if (S.view === "lobby") renderLobby();
  }

  async function restoreActiveRun() {
    const runId = store.get(RUN_KEY);
    if (!runId) return false;
    try {
      const payload = await api("/runs/" + encodeURIComponent(runId));
      if (payload && payload.run && payload.run.status === "active") {
        if (S.traineeId !== payload.trainee.id) {
          await selectTrainee(payload.trainee.id, { silent: true });
        }
        S.run = payload;
        S.lastTurn = null;
        S.lastHint = null;
        renderBattleTab();
        return true;
      }
    } catch (err) {
      /* 记录不存在则清除 */
    }
    store.del(RUN_KEY);
    return false;
  }

  /* ---------------- 顶栏 ---------------- */

  function renderLlm(health, failed) {
    const chip = $("#llm-chip");
    if (!chip) return;
    const dot = $(".dot", chip);
    const text = $(".text", chip);
    if (!health) {
      chip.className = "llm-chip" + (failed ? " off" : "");
      text.textContent = failed ? "本地模型离线 · 模板兜底" : "模型连接中";
      chip.title = "正在探测本地 Ollama 服务";
      return;
    }
    if (health.available) {
      chip.className = "llm-chip ok";
      text.textContent = (health.model || "本地模型") + " · 本地推理";
      chip.title =
        (health.base_url || "") + " · 已发现 " + (health.models ? health.models.length : 0) + " 个模型";
    } else {
      chip.className = "llm-chip warn";
      text.textContent = "模型未就绪 · 模板兜底";
      chip.title = health.error || "Ollama 不可用";
    }
    if (dot) dot.setAttribute("aria-hidden", "true");
  }

  function renderTopbar() {
    const p = S.progress;
    const avatar = $("#trainee-btn-avatar");
    const name = $("#trainee-btn-name");
    const rank = $("#trainee-btn-rank");
    if (p && p.trainee) {
      avatar.textContent = p.trainee.avatar || "🎮";
      name.textContent = p.trainee.name;
      rank.textContent = p.rank.name + " · " + fmtInt(p.rank.xp) + " XP";
    } else {
      avatar.textContent = "🎮";
      name.textContent = "选择学员";
      rank.textContent = "—";
    }
    renderTraineeMenu();
    renderBattleTab();
  }

  function renderTraineeMenu() {
    const menu = $("#trainee-menu");
    if (!menu) return;
    const items = S.trainees
      .map(function (t) {
        const active = t.id === S.traineeId;
        return (
          '<button class="dropdown-item' + (active ? " active" : "") + '" data-act="switch-trainee" data-id="' +
          esc(t.id) + '" role="menuitem">' +
          '<span class="avatar">' + esc(t.avatar) + "</span>" +
          '<span class="meta"><b>' + esc(t.name) + "</b><small>" + esc(t.rank) + " · " + fmtInt(t.xp) + " XP</small></span>" +
          (active ? '<span class="check">✓</span>' : "") +
          "</button>"
        );
      })
      .join("");
    menu.innerHTML =
      items +
      '<div class="dropdown-sep"></div>' +
      '<button class="dropdown-add" data-act="new-trainee">＋ 新建学员档案</button>';
  }

  function toggleTraineeMenu() {
    const menu = $("#trainee-menu");
    if (!menu) return;
    renderTraineeMenu();
    const isHidden = menu.classList.contains("hidden");
    menu.classList.toggle("hidden");
    $("#trainee-btn").setAttribute("aria-expanded", isHidden ? "true" : "false");
  }

  function closeTraineeMenu() {
    const menu = $("#trainee-menu");
    if (!menu || menu.classList.contains("hidden")) return;
    menu.classList.add("hidden");
    $("#trainee-btn").setAttribute("aria-expanded", "false");
  }

  function renderBattleTab() {
    const tab = $("#tab-battle");
    if (!tab) return;
    const active = !!(S.run && S.run.run && S.run.run.status === "active");
    tab.hidden = !active;
  }

  /* ---------------- 视图切换 ---------------- */

  function setView(view) {
    const changed = S.view !== view;
    if (view === "battle" && !(S.run && S.run.run && S.run.run.status === "active")) {
      toast("当前没有进行中的对练", "info");
      view = "lobby";
    }
    if (S.view === "battle" && view !== "battle") {
      const input = $("#chat-input");
      if (input) S.draft = input.value;
    }
    S.view = view;
    $("#view-lobby").hidden = view !== "lobby";
    $("#view-battle").hidden = view !== "battle";
    $("#view-admin").hidden = view !== "admin";
    $$(".tab").forEach(function (tab) {
      tab.classList.toggle("active", tab.dataset.view === view);
    });
    renderBattleTab();
    closeTraineeMenu();
    // 切换页面时回到顶部，避免从大厅中部进入对练时看不到顶部信息
    if (changed) window.scrollTo(0, 0);

    if (view === "lobby") {
      stopClock();
      renderLobby();
    } else if (view === "battle") {
      renderBattle();
      const input = $("#chat-input");
      if (input && S.draft) {
        input.value = S.draft;
        autoGrow(input);
      }
    } else if (view === "admin") {
      stopClock();
      loadAdmin();
    }
  }

  /* ---------------- 大厅 ---------------- */

  function renderLobby() {
    const p = S.progress;
    const hero = $("#lobby-hero");
    if (!p) {
      hero.innerHTML =
        '<div class="panel profile-card" style="grid-column:1/-1;padding:48px 30px;align-items:flex-start;gap:16px">' +
        '<p class="eyebrow">Trainee Profile</p><h1 style="font-size:24px">还没有训练档案</h1>' +
        '<p class="muted">创建一名学员，开始第一场 AI 实战对练。</p>' +
        '<div style="display:flex;gap:9px"><button class="btn primary" data-act="new-trainee">新建学员</button>' +
        '<button class="btn ghost" data-act="view-admin">查看数据看板</button></div></div>';
      $("#badge-strip").innerHTML = "";
      $("#level-map").innerHTML = "";
      $("#recent-runs").innerHTML = "";
      return;
    }

    const rank = p.rank || {};
    const stats = p.stats || {};
    const levels = p.levels || [];
    const badges = p.badges || [];
    const passedCount = levels.filter((l) => l.passed).length;
    const earnedBadges = badges.filter((b) => b.earned).length;
    const tone = rank.color || "#37e1ff";
    const recommended = levels.find((l) => l.unlocked && !l.passed) || null;

    const nextXpText =
      rank.next_xp != null
        ? "距 " + esc(rank.next_name) + " 还需 " + fmtInt(Math.max(0, rank.next_xp - rank.xp)) + " XP"
        : "已达最高段位";
    const bestLatency = stats.best_latency_s ? fmtOne(stats.best_latency_s) + " 秒" : "—";

    const profileHtml =
      '<div class="panel profile-card" style="--tone:' + esc(tone) + '">' +
      '<span class="corner" aria-hidden="true"></span>' +
      '<div class="profile-main">' +
      '<div class="profile-avatar">' + esc(p.trainee.avatar) + '<span class="status-dot"></span></div>' +
      '<div class="profile-info">' +
      '<p class="eyebrow">Trainee Profile · ' + esc((S.meta && S.meta.tenant && S.meta.tenant.name) || "企业租户") + "</p>" +
      '<div class="profile-name-row"><h1>' + esc(p.trainee.name) + "</h1>" +
      '<span class="rank-chip" style="--tone:' + esc(tone) + '">' + esc(rank.name) + " · 第 " + (rank.tier_index || 1) + "/" + (rank.tier_total || 6) + " 段</span></div>" +
      '<p class="profile-sub">已通关 ' + passedCount + " / " + levels.length + " 关 · 累计 " + fmtInt(stats.attempts) + " 次训练 · 平均分 " + (stats.avg_score || 0) + "</p>" +
      "</div></div>" +
      '<div class="xp-block"><div class="xp-head"><span>成长值 / XP</span><b>' + fmtInt(rank.xp) + " <em>XP</em></b></div>" +
      '<div class="xp-track"><i style="width:' + (rank.progress || 0) + '%"></i></div>' +
      '<div class="xp-foot"><span>' + esc(rank.name) + "</span><span>" + nextXpText + "</span></div></div>" +
      '<div class="profile-stats">' +
      '<div class="stat-cell"><strong>' + passedCount + "<small> / " + levels.length + "</small></strong><span>已通关卡</span></div>" +
      '<div class="stat-cell"><strong>' + (stats.avg_score || 0) + "<small> 分</small></strong><span>平均得分</span></div>" +
      '<div class="stat-cell"><strong>' + bestLatency + "</strong><span>最佳首响</span></div>" +
      '<div class="stat-cell"><strong>' + earnedBadges + "<small> / " + badges.length + "</small></strong><span>成就徽章</span></div>" +
      "</div></div>";

    let nextHtml = "";
    if (recommended) {
      const lv = recommended;
      const persona = lv.persona_public || { avatar: "🎭", name: "神秘玩家", title: "" };
      const lvTone = lv.tier_color || "#37e1ff";
      nextHtml =
        '<div class="panel next-card" style="--tone:' + esc(lvTone) + '">' +
        '<div class="next-head"><p class="eyebrow">Next Mission · 下一关</p>' +
        '<span class="tier-chip" style="--tone:' + esc(lvTone) + '">' + esc(lv.tier) + "</span></div>" +
        '<div class="next-title"><h2>' + esc(lv.name) + "</h2></div>" +
        '<p class="next-sub">' + esc(lv.subtitle) + " · " + esc(lv.difficulty) + "</p>" +
        '<div class="persona-row"><span class="persona-avatar">' + esc(persona.avatar) + "</span>" +
        '<div class="who"><b>' + esc(persona.name) + "</b><small>" + esc(persona.title) + "</small></div>" +
        '<span class="tag">' + esc((persona.tags || [])[0] || "AI 玩家") + "</span></div>" +
        '<div class="next-meta"><span><i></i>' + (lv.objectives ? lv.objectives.length : 5) + " 个考核目标</span>" +
        "<span><i></i>建议 " + lv.suggested_turns + " 回合</span><span><i></i>+" + lv.xp + " XP</span>" +
        "<span><i></i>通过线 " + lv.pass_score + "</span></div>" +
        '<div class="next-actions"><button class="btn primary" data-act="start-level" data-level="' + esc(lv.id) + '">开始对练</button>' +
        '<button class="btn ghost" data-act="brief-level" data-level="' + esc(lv.id) + '">任务简报</button></div>' +
        "</div>";
    } else {
      nextHtml =
        '<div class="panel next-card cleared-card" style="--tone:#ffc857">' +
        '<div class="next-head"><p class="eyebrow">All Cleared · 全关卡通关</p><span class="tier-chip" style="--tone:#ffc857">王者</span></div>' +
        '<div class="next-title"><h2>训练地图已点亮</h2></div>' +
        '<div class="cleared-seal"><span class="seal">👑</span><div><b>' + passedCount + " / " + levels.length + " 关全部通过</b>" +
        "<small>可以复训刷新最佳成绩，或去看板观察团队能力变化。</small></div></div>" +
        '<div class="next-meta"><span><i></i>平均分 ' + (stats.avg_score || 0) + "</span><span><i></i>最佳 " + (stats.best_score || 0) + " 分</span></div>" +
        '<div class="next-actions"><button class="btn primary" data-act="view-admin">查看数据看板</button>' +
        '<button class="btn ghost" data-act="brief-level" data-level="king-1">复训王者关</button></div>' +
        "</div>";
    }

    hero.innerHTML = profileHtml + nextHtml;
    renderBadges(badges);
    renderLevelMap(levels, recommended);
    renderRecent(p.recent_runs || [], levels);
  }

  function renderBadges(badges) {
    const wrap = $("#badge-strip");
    const earned = badges.filter((b) => b.earned).length;
    wrap.innerHTML =
      '<div class="strip-title"><b>成就徽章</b><small>已获得 ' + earned + " / " + badges.length + '</small></div>' +
      badges
        .map(function (b) {
          return (
            '<span class="badge-item' + (b.earned ? " earned" : "") + '" title="' + esc(b.desc) + '">' +
            '<span class="icon">' + esc(b.icon) + "</span>" + esc(b.name) +
            (b.earned ? "" : "<em>未解锁</em>") + "</span>"
          );
        })
        .join("");
  }

  function renderLevelMap(levels, recommended) {
    const map = $("#level-map");
    const tiers = [];
    levels.forEach(function (lv) {
      let group = tiers.find((g) => g.tier === lv.tier);
      if (!group) {
        group = { tier: lv.tier, color: lv.tier_color || "#37e1ff", levels: [] };
        tiers.push(group);
      }
      group.levels.push(lv);
    });

    map.innerHTML = tiers
      .map(function (group) {
        const passed = group.levels.filter((l) => l.passed).length;
        const cards = group.levels
          .map(function (lv) {
            const persona = lv.persona_public || { avatar: "🎭" };
            const isRec = recommended && recommended.id === lv.id;
            const stateClass = lv.passed ? "passed" : lv.unlocked ? "ready" : "locked";
            let stateLabel = lv.passed ? "已通关" : lv.unlocked ? "可挑战" : "未解锁";
            let bestText = "尚未挑战";
            let cta = "查看简报 →";
            if (lv.passed) {
              bestText = "最佳 <b>" + (lv.best_score == null ? "—" : lv.best_score) + "</b>";
              cta = "再练一次 →";
            } else if (lv.unlocked && lv.best_score != null) {
              bestText = "最佳 <b>" + lv.best_score + "</b>";
            } else if (!lv.unlocked) {
              bestText = "通过上一关解锁";
              cta = "未解锁";
            }
            return (
              '<button type="button" class="level-card ' + stateClass + (isRec ? " recommended" : "") +
              '" style="--tone:' + esc(lv.tier_color || "#37e1ff") + '" data-act="brief-level" data-level="' +
              esc(lv.id) + '" data-locked="' + (lv.unlocked ? "0" : "1") + '">' +
              '<div class="level-top"><span class="level-no">' + String(lv.order).padStart(2, "0") + "</span>" +
              '<span class="persona-avatar sm">' + esc(persona.avatar) + "</span>" + '<span class="state-chip">' + stateLabel + "</span></div>" +
              "<h3>" + esc(lv.name) + "<small>" + esc(lv.subtitle) + "</small></h3>" +
              '<div class="level-tags"><span>' + esc(lv.difficulty) + "</span><span>" +
              (lv.objectives ? lv.objectives.length : 5) + " 个目标</span><span>" + esc(lv.tier) + "</span></div>" +
              '<div class="level-bottom"><span class="level-best">' + bestText + '</span><span class="level-cta">' + cta + "</span></div>" +
              "</button>"
            );
          })
          .join("");
        return (
          '<div class="tier-group">' +
          '<div class="tier-head" style="--tone:' + esc(group.color) + '">' +
          '<span class="tier-flag"><i></i>' + esc(group.tier) + "训练营</span><span class=\"thread\"></span>" +
          '<span class="tier-count">' + passed + " / " + group.levels.length + " 已通关</span></div>" +
          '<div class="level-grid">' + cards + "</div></div>"
        );
      })
      .join("");
  }

  function renderRecent(runs, levels) {
    const wrap = $("#recent-runs");
    if (!runs.length) {
      wrap.innerHTML =
        '<div class="panel recent-panel"><div class="recent-head"><h3>最近训练</h3></div>' +
        '<div class="recent-empty">还没有训练记录，选择一个关卡开始第一次对练。</div></div>';
      return;
    }
    const rows = runs
      .map(function (r, i) {
        const lv = levels.find((l) => l.id === r.level_id) || levelById(r.level_id) || {};
        const statusClass = r.status === "passed" ? "passed" : "failed";
        const statusText = r.status === "passed" ? "通过" : "未通过";
        return (
          '<div class="recent-row" data-act="view-run" data-run="' + esc(r.id) + '" style="cursor:pointer">' +
          '<span class="idx">' + String(i + 1).padStart(2, "0") + "</span>" +
          '<div class="lv"><b>' + esc(lv.name || r.level_id) + "</b><small>" + (lv.tier ? esc(lv.tier) + " · " : "") + esc(lv.subtitle || "") + "</small></div>" +
          '<span class="status-chip ' + statusClass + '">' + statusText + "</span>" +
          '<span class="score">' + (r.total_score == null ? "—" : r.total_score) + " <small>分</small></span>" +
          '<span class="when">首响 ' + fmtOne(r.avg_latency_s) + "s</span>" +
          '<span class="when">' + esc(relTime(r.finished_at)) + "</span>" +
          "</div>"
        );
      })
      .join("");
    wrap.innerHTML =
      '<div class="panel recent-panel"><div class="recent-head"><h3>最近训练</h3>' +
      '<span class="muted">点击任意一局查看复盘</span></div><div class="recent-list">' + rows + "</div></div>";
  }

  /* ---------------- 任务简报 ---------------- */

  function levelById(id) {
    if (S.progress && S.progress.levels) {
      const lv = S.progress.levels.find((x) => x.id === id);
      if (lv) return lv;
    }
    if (S.meta && S.meta.levels) {
      return S.meta.levels.find((x) => x.id === id) || null;
    }
    return null;
  }

  function metaLevelById(id) {
    if (S.meta && S.meta.levels) return S.meta.levels.find((x) => x.id === id) || null;
    return null;
  }

  function openBriefing(levelId) {
    const lv = levelById(levelId);
    if (!lv) {
      toast("关卡不存在", "error");
      return;
    }
    if (lv.unlocked === false) {
      toast("请先通过上一关，再挑战本关", "warn");
      return;
    }
    const persona = lv.persona_public || { avatar: "🎭", name: "神秘玩家", title: "", tags: [], background: "", personality: "" };
    const metaLv = metaLevelById(levelId);
    const knowledge = (metaLv && metaLv.knowledge) || (lv.knowledge || []);
    const tone = lv.tier_color || "#37e1ff";
    const focus = String(lv.coach_focus || "").split("·").map((s) => s.trim()).filter(Boolean);
    const objectives = lv.objectives || [];

    const objHtml = objectives
      .map(function (o) {
        return (
          '<div class="obj-preview-row"><span class="dot"></span><span class="lb">' + esc(o.label) +
          '</span><span class="wt">' + o.weight + " 分</span></div>"
        );
      })
      .join("");

    const kbHtml = knowledge.length
      ? knowledge
          .map(function (doc) {
            return (
              '<details class="kb-preview-item"><summary>📚 ' + esc(doc.title) + "</summary>" +
              '<div class="body">' + esc(doc.content) + "</div></details>"
            );
          })
          .join("")
      : '<p class="muted">本关暂无关联知识文档</p>';

    openModal(
      '<button class="modal-close" data-act="close-modal" aria-label="关闭">✕</button>' +
        '<div class="modal-head"><p class="eyebrow">Mission Brief · ' + esc(lv.tier) + "训练营</p>" +
        '<h2>' + esc(lv.name) + ' <span class="muted" style="font-size:13px">' + esc(lv.subtitle) + "</span></h2>" +
        "<p>" + esc(lv.coach_focus) + "</p></div>" +
        '<div class="modal-section"><h4>情景背景</h4><div class="scene-box">' + esc(lv.scene) + "</div></div>" +
        '<div class="modal-section"><h4>教练提示</h4><div class="scene-box" style="border-left-color:var(--gold);background:rgba(255,200,87,.055);color:#e8d9b8">' +
        esc(lv.brief) + "</div></div>" +
        '<div class="modal-section"><h4>对练对象</h4><div class="persona-intel">' +
        '<span class="persona-avatar" style="border-color:' + esc(persona.color || tone) + '">' + esc(persona.avatar) + "</span>" +
        '<div class="who"><b>' + esc(persona.name) + "</b><small>" + esc(persona.title) + "</small>" +
        '<div class="tags">' + (persona.tags || []).map((t) => "<span>" + esc(t) + "</span>").join("") + "</div>" +
        '<p>' + esc(persona.background || persona.personality || "") + "</p></div></div></div>" +
        '<div class="modal-section"><h4>教练关注点</h4><div class="focus-line">' +
        focus.map((f) => "<span>" + esc(f) + "</span>").join("") + "</div></div>" +
        '<div class="modal-section"><h4>考核目标</h4><div class="obj-preview">' + objHtml + "</div></div>" +
        '<div class="modal-section"><h4>知识库</h4><div class="kb-preview">' + kbHtml + "</div></div>" +
        '<div class="brief-facts">' +
        '<div class="f"><span>难度</span><b style="font-size:12px">' + esc(lv.difficulty) + "</b></div>" +
        '<div class="f"><span>建议回合</span><b>' + lv.suggested_turns + "</b></div>" +
        '<div class="f"><span>通过线</span><b>' + lv.pass_score + "</b></div>" +
        '<div class="f"><span>关卡奖励</span><b>+' + lv.xp + " XP</b></div></div>" +
        '<div class="modal-actions"><button class="btn ghost" data-act="close-modal">取消</button>' +
        '<button class="btn primary" data-act="start-level" data-level="' + esc(lv.id) + '">' +
        (lv.passed ? "再练一次" : "开始对练") + "</button></div>"
    );
  }

  /* ---------------- 对练 ---------------- */

  function lastPlayerAt(payload) {
    const players = (payload.transcript || []).filter((m) => m.role === "player");
    if (players.length) return players[players.length - 1].created_at;
    return payload.run ? payload.run.started_at : null;
  }

  function renderBattle() {
    const p = S.run;
    if (!p) return;
    const lv = p.level;
    const persona = p.persona;
    const trainee = p.trainee;
    const tone = lv.tier_color || "#37e1ff";

    $("#battle-head").innerHTML =
      '<button class="back-btn" data-act="back-lobby">← 返回大厅</button>' +
      '<div class="battle-title"><p class="eyebrow">Live Drill · ' + esc(lv.tier) + "训练营</p>" +
      "<h1>" + esc(lv.name) + '<span class="muted">' + esc(lv.subtitle) + "</span></h1></div>" +
      '<span class="pill">' + esc(trainee.avatar) + " " + esc(trainee.name) + "</span>" +
      '<span class="pill">' + esc(lv.difficulty) + "</span>" +
      '<span class="pill">通过线 ' + lv.pass_score + "</span>" +
      '<div class="spacer"></div>' +
      '<div class="resp-timer" id="resp-timer"><span class="lbl">RESPONSE<b>首响计时</b></span><span class="clock">00:00</span></div>' +
      '<div class="turn-chip">回合 <b id="turn-current">' + p.run.turn_count + "</b>/" + lv.max_turns + "</div>" +
      '<button class="btn ghost" id="finish-btn" data-act="finish">结束并结算</button>';

    const focus = esc(lv.coach_focus || "");
    $("#battle-brief").innerHTML =
      '<p class="panel-label">Mission Brief · 任务简报</p>' +
      '<div class="brief-title"><h3>' + esc(lv.name) + '</h3><span class="tier-chip" style="--tone:' + esc(tone) + '">' + esc(lv.tier) + "</span></div>" +
      '<div class="brief-persona"><span class="persona-avatar">' + esc(persona.avatar) + "</span>" +
      '<div class="who"><b>' + esc(persona.name) + "</b><small>" + esc(persona.title) + "</small></div></div>" +
      '<p class="brief-focus">' + focus + "</p>" +
      '<p class="panel-label" style="margin-bottom:7px">Live SOP · 实时目标</p>' +
      '<div class="objective-progress"><div class="bar"><i id="obj-bar" style="width:0%"></i></div>' +
      '<span class="txt" id="obj-count">0 / 100</span></div>' +
      '<div class="obj-list" id="obj-list"></div>' +
      '<div class="brief-foot"><span>💡 提示 −2 分 / 次</span><span>建议 ' + lv.suggested_turns + " 回合</span></div>";

    const docs = lv.knowledge || [];
    $("#battle-knowledge").innerHTML =
      '<p class="panel-label">Knowledge · 知识库</p>' +
      (docs.length
        ? '<div class="kb-list">' +
          docs
            .map(function (doc) {
              return (
                '<div class="kb-item"><button class="kb-toggle" data-act="toggle-kb" data-kb="' + esc(doc.id) + '">' +
                '<span class="icon">📚</span><span class="t">' + esc(doc.title) + '</span><span class="chev">▾</span></button>' +
                '<div class="kb-body" id="kb-' + esc(doc.id) + '" hidden>' + esc(doc.content) +
                '<div class="tags">' + (doc.tags || []).map((t) => "<span>" + esc(t) + "</span>").join("") + "</div></div></div>"
              );
            })
            .join("") +
          "</div>"
        : '<p class="hint-body empty"><span class="bulb">📚</span><span>本关暂无关联知识文档。</span></p>');

    $("#chat-persona").innerHTML =
      '<span class="persona-avatar" style="border-color:' + esc(persona.color || tone) + '">' + esc(persona.avatar) + "</span>" +
      '<div class="who"><b>' + esc(persona.name) + "</b><small>" + esc(persona.title) + " · " +
      esc((persona.tags || []).join(" / ")) + "</small></div>";
    $("#typing-avatar").textContent = persona.avatar;
    $("#typing-text").textContent = "玩家正在输入…";
    $("#chat-status-text").textContent = p.run.status === "active" ? "在线 · 等待接待" : "本局已结束";

    S.lastPlayerAt = lastPlayerAt(p);
    S.lastTurn = null;
    S.lastHint = null;

    renderChat(p);
    renderObjectives(p, []);
    renderEmotionPanel(p, null);
    renderHintPanel();
    renderAiPanel(p, null);
    updateComposer();
    startClock();
  }

  function renderObjectives(payload, justMet) {
    const list = $("#obj-list");
    if (!list) return;
    const flash = justMet || [];
    const objectives = payload.objectives || [];
    const metWeight = objectives.filter((o) => o.met).reduce((sum, o) => sum + (o.weight || 0), 0);
    const bar = $("#obj-bar");
    const count = $("#obj-count");
    if (bar) bar.style.width = Math.max(0, Math.min(100, metWeight)) + "%";
    if (count) count.textContent = metWeight + " / 100";
    list.innerHTML = objectives
      .map(function (o) {
        return (
          '<div class="obj-row' + (o.met ? " met" : "") + (flash.indexOf(o.key) >= 0 ? " just-met" : "") +
          '"><span class="dot">✓</span><span class="label">' + esc(o.label) +
          '</span><span class="w">' + o.weight + "</span></div>"
        );
      })
      .join("");
  }

  function renderChat(payload) {
    const log = $("#chat-log");
    if (!log) return;
    const persona = payload.persona;
    const trainee = payload.trainee;
    const objectives = (payload.level && payload.level.objectives) || [];
    const labelMap = {};
    objectives.forEach(function (o) {
      labelMap[o.key] = o.label;
    });

    const html = (payload.transcript || [])
      .map(function (m) {
        if (m.role === "system") {
          return '<div class="sys-divider">' + esc(m.content) + "</div>";
        }
        if (m.role === "player") {
          return (
            '<div class="msg-row player" style="--persona:' + esc(persona.color || "#8ca7ff") + '">' +
            '<span class="msg-avatar">' + esc(persona.avatar) + '</span><div class="msg-block">' +
            '<div class="msg-meta"><b>' + esc(persona.name) + '</b><span class="time">' + fmtTime(m.created_at) + "</span></div>" +
            '<div class="bubble">' + esc(m.content) + "</div></div></div>"
          );
        }
        const analysis = m.analysis || {};
        const tags = [];
        (analysis.new_objectives || []).forEach(function (key) {
          if (labelMap[key]) tags.push('<span>✓ ' + esc(labelMap[key]) + "</span>");
        });
        if ((analysis.forbidden || []).length) tags.push('<span class="warn">⚠ 出现服务忌语</span>');
        if ((analysis.over_promise || []).length) tags.push('<span class="warn">⚠ 越权承诺</span>');
        const lat = m.latency_ms != null
          ? '<span class="lat" style="color:' + latencyColor(m.latency_ms) + '">首响 ' + latencyText(m.latency_ms) + "</span>"
          : "";
        return (
          '<div class="msg-row trainee">' +
          '<span class="msg-avatar">' + esc(trainee.avatar) + '</span><div class="msg-block">' +
          '<div class="msg-meta"><b>我 · 客服</b><span class="time">' + fmtTime(m.created_at) + "</span>" + lat + "</div>" +
          '<div class="bubble">' + esc(m.content) + "</div>" +
          (tags.length ? '<div class="msg-tags">' + tags.join("") + "</div>" : "") +
          "</div></div>"
        );
      })
      .join("");
    log.innerHTML = html;
    scrollChat();
  }

  function scrollChat() {
    const log = $("#chat-log");
    if (!log) return;
    log.scrollTop = log.scrollHeight;
  }

  function renderEmotionPanel(payload, delta) {
    const panel = $("#emotion-panel");
    if (!panel) return;
    const value = Math.max(1, Math.min(10, payload.run.emotion || 5));
    const meta = emotionMeta(value);
    const deltaHtml = delta
      ? '<span class="emotion-delta ' + (delta > 0 ? "up" : "down") + ' show" id="emotion-delta">' +
        (delta > 0 ? "+" : "") + delta + "</span>"
      : "";
    panel.innerHTML =
      '<p class="panel-label">Player Emotion · 玩家情绪</p>' + deltaHtml +
      '<div class="emotion-head"><span class="emotion-face">' + meta.face + "</span>" +
      '<div><div class="emotion-value"><b>' + value + '</b><small>/ 10</small></div>' +
      '<div class="emotion-label" style="color:' + meta.color + '">' + meta.label + "</div></div></div>" +
      '<div class="emotion-track" style="--emotion-color:' + meta.color + '">' +
      '<div class="emotion-fill" style="width:' + value * 10 + '%"></div>' +
      '<span class="emotion-marker" style="left:' + value * 10 + '%"></span></div>' +
      '<div class="emotion-scale"><span>1 平静</span><span>5 观望</span><span>10 爆发</span></div>' +
      '<p class="emotion-note" style="--emotion-color:' + meta.color + '">' + meta.note + "</p>";
    if (delta) {
      setTimeout(function () {
        const el = $("#emotion-delta");
        if (el) el.classList.remove("show");
      }, 2200);
    }
  }

  function renderHintPanel() {
    const panel = $("#hint-panel");
    if (!panel) return;
    const used = S.run && S.run.run ? S.run.run.hints_used || 0 : 0;
    let body;
    if (S.lastHint && S.lastHint.hint) {
      body =
        '<div class="hint-label">🎯 下一个目标 · ' + esc(S.lastHint.label) + "</div>" +
        '<div class="hint-text">' + esc(S.lastHint.hint) + "</div>" +
        '<div class="hint-uses"><span>提示已用 ' + used + " / " + MAX_HINTS + "</span><span>−" + Math.min(6, used * 2) + " 分</span></div>";
    } else if (S.lastHint && S.lastHint.message) {
      body = '<div class="hint-text" style="border-color:var(--line);background:rgba(255,255,255,.03);color:var(--muted)">' +
        esc(S.lastHint.message) + "</div>" +
        '<div class="hint-uses"><span>提示已用 ' + used + " / " + MAX_HINTS + "</span><span>−" + Math.min(6, used * 2) + " 分</span></div>";
    } else {
      body =
        '<div class="hint-body empty"><span class="bulb">💡</span><span>卡住时点击输入框上方的「战术提示」，获取下一个 SOP 动作；每次扣 2 分。</span></div>';
    }
    panel.innerHTML = '<p class="panel-label">Tactical Hint · 战术提示</p>' + body;
  }

  function renderAiPanel(payload, turn) {
    const panel = $("#ai-panel");
    if (!panel) return;
    const ai = payload.ai || {};
    const online = !!ai.available;
    const fallback = turn && turn.ai_fallback;
    const latency = turn && turn.ai_latency_ms;
    const used = payload.run ? payload.run.hints_used || 0 : 0;
    panel.innerHTML =
      '<p class="panel-label">AI Engine · 推理引擎</p>' +
      '<div class="ai-engine"><span class="ai-orb"></span><div class="who"><b>LOCAL AI PLAYER</b>' +
      "<small>" + esc(online ? ai.model || "本地模型" : "模板兜底模式") + "</small></div></div>" +
      '<div class="ai-rows">' +
      '<div><span class="k">连接状态</span><span class="v ' + (online ? "good" : "warn") + '">' +
      (online ? "本地在线" : "离线兜底") + "</span></div>" +
      '<div><span class="k">本轮回复</span><span class="v">' + (latency ? fmtOne(latency / 1000) + " s" : "—") + "</span></div>" +
      '<div><span class="k">评分引擎</span><span class="v">规则 40 · AI 60</span></div>' +
      '<div><span class="k">提示扣分</span><span class="v">' + Math.min(6, used * 2) + " / 6</span></div></div>" +
      '<p class="ai-note">' +
      (fallback
        ? "本轮模型未返回内容，已使用人设模板台词，训练与评分不受影响。"
        : online
        ? "通过 Ollama 本地推理，对话数据不出本机，符合企业隐私要求。"
        : "未检测到本地模型，AI 玩家使用人设模板兜底，保证演练可继续。") +
      "</p>";
  }

  function updateBattle(payload, turn) {
    S.run = payload;
    store.set(RUN_KEY, payload.run.id);
    S.lastPlayerAt = lastPlayerAt(payload);
    S.lastTurn = turn || S.lastTurn;
    const current = $("#turn-current");
    if (current) current.textContent = payload.run.turn_count;
    $("#chat-status-text").textContent = payload.run.status === "active" ? "在线 · 等待接待" : "本局已结束";
    renderChat(payload);
    renderObjectives(payload, turn && turn.new_objectives ? turn.new_objectives.map((o) => o.key) : []);
    renderEmotionPanel(payload, turn ? turn.emotion_delta : null);
    renderHintPanel();
    renderAiPanel(payload, S.lastTurn);
    updateComposer();
    startClock();
  }

  function updateComposer() {
    const p = S.run;
    if (!p) return;
    const input = $("#chat-input");
    const send = $("#send-btn");
    const hint = $("#hint-btn");
    const finish = $("#finish-btn");
    const note = $("#composer-note");
    if (!input || !send) return;
    const active = p.run.status === "active";
    const maxed = p.run.turn_count >= p.level.max_turns;
    const disabled = !active || maxed || S.busy;
    input.disabled = disabled;
    send.disabled = disabled;
    if (hint) hint.disabled = !active || S.busy || (p.run.hints_used || 0) >= MAX_HINTS;
    if (finish) finish.disabled = !active || S.busy || p.run.turn_count < 1;
    if (!active) {
      input.placeholder = "本局已结束";
      if (note) note.textContent = "本局已结束，可返回大厅开始新的对练";
    } else if (maxed) {
      input.placeholder = "已达回合上限，请结束并结算";
      if (note) note.textContent = "已达 " + p.level.max_turns + " 回合上限，请结束对练结算";
    } else if (S.busy) {
      if (note) note.textContent = "AI 玩家正在组织语言…";
    } else {
      input.placeholder = "以客服身份回复玩家…（Enter 发送，Shift + Enter 换行）";
      if (note) note.textContent = "Enter 发送 · 每条回复都会被实时分析";
    }
    if (note) note.classList.toggle("warn", active && maxed);
  }

  function startClock() {
    stopClock();
    if (!S.run || S.run.run.status !== "active") return;
    updateClock();
    S.clockTimer = setInterval(updateClock, 500);
  }

  function stopClock() {
    if (S.clockTimer) {
      clearInterval(S.clockTimer);
      S.clockTimer = null;
    }
  }

  function updateClock() {
    if (!S.run || S.run.run.status !== "active" || S.busy) return;
    const wrap = $("#resp-timer");
    const clock = wrap ? $(".clock", wrap) : null;
    if (!wrap || !clock) return;
    const start = Date.parse(S.lastPlayerAt || "");
    if (!start) {
      clock.textContent = "—";
      return;
    }
    const secs = Math.max(0, Math.floor((Date.now() - start) / 1000));
    clock.textContent = formatClock(secs);
    wrap.classList.toggle("warn", secs > 30 && secs <= 60);
    wrap.classList.toggle("hot", secs > 60);
  }

  function autoGrow(el) {
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(150, Math.max(54, el.scrollHeight)) + "px";
  }

  function showTyping(text) {
    const typing = $("#typing");
    if (!typing) return;
    $("#typing-text").textContent = text || "玩家正在输入…";
    typing.classList.remove("hidden");
  }

  function hideTyping() {
    const typing = $("#typing");
    if (!typing) return;
    typing.classList.add("hidden");
  }

  function appendPending(text) {
    const log = $("#chat-log");
    if (!log || !S.run) return;
    const el = document.createElement("div");
    el.className = "msg-row trainee";
    el.id = "pending-msg";
    el.innerHTML =
      '<span class="msg-avatar">' + esc(S.run.trainee.avatar) + '</span><div class="msg-block">' +
      '<div class="msg-meta"><b>我 · 客服</b><span class="time">' + fmtTime(new Date().toISOString()) + "</span></div>" +
      '<div class="bubble pending">' + esc(text) + "</div></div>";
    log.appendChild(el);
    scrollChat();
  }

  function removePending() {
    const el = $("#pending-msg");
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  async function sendMessage() {
    const p = S.run;
    if (!p || S.busy) return;
    if (p.run.status !== "active") return;
    const input = $("#chat-input");
    if (!input) return;
    if (p.run.turn_count >= p.level.max_turns) {
      toast("已达回合上限，请结束对练结算", "warn");
      return;
    }
    const text = input.value.trim();
    if (!text) {
      toast("请输入回复内容", "warn");
      return;
    }

    input.value = "";
    autoGrow(input);
    S.busy = true;
    appendPending(text);
    showTyping("玩家正在输入…");
    updateComposer();
    startClock();

    try {
      const payload = await api("/runs/" + encodeURIComponent(p.run.id) + "/messages", {
        method: "POST",
        body: { content: text },
      });
      const turn = payload.turn || {};
      const justMet = (turn.new_objectives || []).map((o) => o.key);
      if (S.lastHint && S.lastHint.key && justMet.indexOf(S.lastHint.key) >= 0) S.lastHint = null;
      updateBattle(payload, turn);
      hideTyping();

      if (turn.new_labels && turn.new_labels.length) {
        toast("🎯 命中 SOP 目标：" + turn.new_labels.join("、"), "success");
      }
      if (turn.analysis && (turn.analysis.forbidden || []).length) {
        toast("⚠ 出现服务忌语：" + turn.analysis.forbidden.slice(0, 3).join("、") + "，情绪稳定度被扣分", "error");
      } else if (turn.analysis && (turn.analysis.over_promise || []).length) {
        toast("⚠ 检测到越权承诺，注意合规边界", "warn");
      }
      if (turn.ai_fallback) {
        toast("本地模型本轮超时，AI 玩家已用模板台词回应", "warn");
      }
      if (payload.run.turn_count >= payload.level.max_turns) {
        toast("已达 " + payload.level.max_turns + " 回合上限，请结束对练结算", "warn");
      }
    } catch (err) {
      removePending();
      hideTyping();
      input.value = text;
      autoGrow(input);
      toast(err.message || "发送失败，请稍后重试", "error");
    } finally {
      S.busy = false;
      hideTyping();
      updateComposer();
      startClock();
      input.focus({ preventScroll: true });
    }
  }

  async function requestHint() {
    if (!S.run || S.busy || S.run.run.status !== "active") return;
    S.busy = true;
    updateComposer();
    try {
      const res = await api("/runs/" + encodeURIComponent(S.run.run.id) + "/hint", { method: "POST" });
      if (S.run && S.run.run) S.run.run.hints_used = res.hints_used || 0;
      if (res.hint) {
        S.lastHint = {
          key: res.hint.key,
          label: res.hint.label,
          hint: res.hint.hint,
          message: res.message,
        };
        toast("💡 " + (res.message || "已获取提示"), "info");
      } else {
        S.lastHint = { message: res.message || "暂时没有可用提示" };
        toast(res.message || "暂时没有可用提示", "warn");
      }
      renderHintPanel();
      renderAiPanel(S.run, S.lastTurn);
    } catch (err) {
      toast(err.message || "获取提示失败", "error");
    } finally {
      S.busy = false;
      updateComposer();
    }
  }

  function openFinishConfirm() {
    if (!S.run || S.busy) return;
    if (S.run.run.turn_count < 1) {
      toast("至少回复一次后才能结算", "warn");
      return;
    }
    const p = S.run;
    const objectives = (p.objectives || []).filter((o) => o.met).length;
    openConfirm({
      title: "结束本局并结算？",
      body:
        "本局已进行 " + p.run.turn_count + " 个回合，完成 " + objectives + " / " + (p.objectives || []).length +
        " 个 SOP 目标，使用提示 " + (p.run.hints_used || 0) + " 次。AI 教练将结合规则引擎与模型评审生成评分。",
      confirmText: "生成评分",
      cancelText: "继续对练",
      onConfirm: finishRun,
    });
  }

  async function finishRun() {
    if (!S.run || S.busy) return;
    closeModal();
    const runId = S.run.run.id;
    S.busy = true;
    stopClock();
    showLoading("AI 教练正在复盘本局…");
    try {
      const payload = await api("/runs/" + encodeURIComponent(runId) + "/finish", { method: "POST" });
      S.run = payload;
      S.lastTurn = null;
      S.lastHint = null;
      S.draft = "";
      S.admin = null;
      store.del(RUN_KEY);
      await loadTrainees();
      await selectTrainee(payload.trainee.id, { silent: true });
      S.busy = false;
      hideLoading();
      renderBattleTab();
      setView("lobby");
      renderResult(payload);
      toast(payload.result && payload.result.passed ? "本局通过，成绩已写入训练档案" : "本局已结算，可复盘后重练", payload.result && payload.result.passed ? "success" : "warn");
    } catch (err) {
      S.busy = false;
      hideLoading();
      updateComposer();
      startClock();
      toast(err.message || "结算失败，请稍后重试", "error");
    }
  }

  async function startRun(levelId) {
    if (!S.traineeId) {
      toast("请先选择或创建一名学员", "warn");
      return;
    }
    if (S.run && S.run.run.status === "active") {
      openConfirm({
        title: "开始新的对练？",
        body: "当前还有一局尚未结算，开始新对练会放弃这一局（不会计入评分）。",
        confirmText: "开始新对练",
        cancelText: "继续当前对练",
        onConfirm: function () {
          doStartRun(levelId);
        },
      });
      return;
    }
    doStartRun(levelId);
  }

  async function doStartRun(levelId) {
    closeModal();
    if (!S.traineeId) {
      toast("请先选择或创建一名学员", "warn");
      return;
    }
    showLoading("正在接入对练通道…");
    try {
      const payload = await api("/runs", {
        method: "POST",
        body: { trainee_id: S.traineeId, level_id: levelId },
      });
      S.run = payload;
      S.lastTurn = null;
      S.lastHint = null;
      S.draft = "";
      store.set(RUN_KEY, payload.run.id);
      hideLoading();
      setView("battle");
      if (payload.ai_fallback) {
        toast("本地模型暂不可用，已切换为模板对话，演练照常进行", "warn");
      }
      setTimeout(function () {
        const input = $("#chat-input");
        if (input) input.focus({ preventScroll: true });
      }, 200);
    } catch (err) {
      hideLoading();
      toast(err.message || "无法开始对练", "error");
    }
  }

  /* ---------------- 提示与复盘弹窗 ---------------- */

  function openResultForRun(runId) {
    showLoading("正在载入训练复盘…");
    api("/runs/" + encodeURIComponent(runId))
      .then(function (payload) {
        hideLoading();
        if (!payload.result) {
          toast("该局尚未结算", "warn");
          return;
        }
        renderResult(payload);
      })
      .catch(function (err) {
        hideLoading();
        toast(err.message || "载入复盘失败", "error");
      });
  }

  function renderResult(payload) {
    const r = payload.result || {};
    const lv = payload.level || {};
    const seeded = !!r.seeded;
    const passed = !!r.passed;
    const total = Math.max(0, Math.min(100, Number(r.total) || 0));
    const grade = r.grade || "D";
    const tone = gradeColor(grade);
    const dims = r.dimensions || [];
    const objectives = r.objectives || [];
    const feedback = r.feedback || [];
    const strengths = r.strengths || [];
    const badgesNew = r.badges_new || [];
    const unlocked = r.unlocked_level || null;
    const next = r.next_level || null;
    const rankBefore = r.rank_before || null;
    const rankAfter = r.rank_after || null;
    const canReplay = !S.progress || !!(S.progress.levels || []).find((x) => x.id === lv.id && x.unlocked);
    // 看板里可能打开其他学员的历史复盘，此时不允许用当前学员直接重练
    const ownRun = !payload.trainee || !S.traineeId || payload.trainee.id === S.traineeId;

    const dimHtml = dims
      .map(function (d) {
        const score = Math.round(Number(d.score) || 0);
        const rule = Math.round(Number(d.rule_score) || 0);
        const judge = d.judge_score == null ? null : Math.round(Number(d.judge_score));
        const color = barColor(score);
        return (
          '<div class="dim-row"><div class="name">' + esc(d.label) +
          "<span>权重 " + Math.round((Number(d.weight) || 0) * 100) + "%</span></div>" +
          '<div class="bar"><i data-width="' + score + '" style="width:0%;--bar-color:' + color + '"></i>' +
          (judge != null ? '<span class="rule-mark" style="left:' + rule + '%" title="规则分 ' + rule + '"></span>' : "") +
          "</div>" +
          '<div class="val" style="color:' + color + '">' + score +
          "<small>" + (judge != null ? "AI " + judge + " · 规则 " + rule : "规则判定") + "</small></div></div>"
        );
      })
      .join("");

    const objHtml = objectives.length
      ? '<div class="modal-section"><h4>SOP 关键点 · 规则判定</h4><div class="obj-result-list">' +
        objectives
          .map(function (o) {
            return (
              '<span class="obj-result' + (o.met ? " met" : "") + '">' + (o.met ? "✓" : "○") + " " +
              esc(o.label) + ' <span class="w">' + (o.weight || 0) + "</span></span>"
            );
          })
          .join("") +
        "</div></div>"
      : "";

    const feedbackHtml = feedback.length
      ? feedback.map(function (f) {
          return '<div class="feedback-item"><span class="ico">▸</span><span>' + esc(f) + "</span></div>";
        }).join("")
      : '<p class="muted">暂无点评</p>';
    const strengthHtml = strengths.length
      ? strengths.map(function (f) {
          return '<div class="feedback-item good"><span class="ico">✦</span><span>' + esc(f) + "</span></div>";
        }).join("")
      : '<p class="muted">本局暂无高亮动作，下一局先稳住共情与流程。</p>';

    const hasRewards =
      r.xp_awarded != null || rankBefore || (badgesNew && badgesNew.length) || unlocked;
    let rewardHtml = "";
    if (hasRewards) {
      const rankTxt = rankAfter
        ? r.rank_up && rankBefore
          ? esc(rankBefore.name) + " → " + esc(rankAfter.name) + " · " + fmtInt(rankAfter.xp) + " XP"
          : esc(rankAfter.name) + " · " + fmtInt(rankAfter.xp) + " XP"
        : "";
      rewardHtml =
        '<div class="reward-strip">' +
        (r.xp_awarded != null
          ? '<div class="reward-item"><span>经验值</span><b>+' + fmtInt(r.xp_awarded) + '</b><span>XP</span></div><div class="reward-sep"></div>'
          : "") +
        (rankAfter
          ? '<div class="reward-item cyan"><span>段位</span><b style="font-size:13px">' + rankTxt + "</b>" +
            (r.rank_up ? '<span class="pill">段位晋升</span>' : "") + "</div>"
          : "") +
        badgesNew
          .map(function (b) {
            return '<div class="reward-item"><span class="badge-mini">' + esc(b.icon) + "</span><span>获得徽章 · " + esc(b.name) + "</span></div>";
          })
          .join("") +
        (unlocked
          ? '<div class="reward-item green"><span>解锁</span><b style="font-size:13px">' + esc(unlocked.name) + "</b></div>"
          : "") +
        "</div>";
    }

    const judgeNote = seeded
      ? "该记录为演示用历史训练数据，仅用于看板分析。"
      : r.judge_available
      ? "AI 教练评审已参与本次评分：规则 40% + AI 60%，提示扣分 " + (r.hint_penalty || 0) + " 分。"
      : r.judge_error || "AI 教练不可用，本局采用纯规则评分。";

    const actionsHtml = !ownRun
      ? '<div class="result-actions"><button class="btn primary" data-act="result-lobby">返回大厅</button></div>' +
        '<p class="judge-note">该复盘属于 ' + esc(payload.trainee.name || "其他学员") +
        "，在顶部切换到该学员后即可再练。</p>"
      : '<div class="result-actions">' +
        (passed && next && !seeded
          ? '<button class="btn ghost" data-act="result-lobby">返回大厅</button>' +
            (canReplay ? '<button class="btn ghost" data-act="start-level" data-level="' + esc(lv.id) + '">再练一次</button>' : "") +
            '<button class="btn primary" data-act="start-level" data-level="' + esc(next.id) + '">挑战下一关 · ' + esc(next.name) + "</button>"
          : seeded
          ? '<button class="btn primary" data-act="result-lobby">返回大厅</button>' +
            (canReplay ? '<button class="btn ghost" data-act="start-level" data-level="' + esc(lv.id) + '">再练一次</button>' : "")
          : '<button class="btn ghost" data-act="result-lobby">返回大厅</button>' +
            (canReplay ? '<button class="btn primary" data-act="start-level" data-level="' + esc(lv.id) + '">再练一次</button>' : "")) +
        "</div>";

    openModal(
      '<button class="modal-close" data-act="close-modal" aria-label="关闭">✕</button>' +
        '<p class="eyebrow">Run Review · ' + esc(lv.tier) + "训练营 · " + esc(lv.name) + "</p>" +
        '<div class="result-head" style="margin-top:10px">' +
        '<div class="score-ring" style="color:' + tone + '"><svg viewBox="0 0 128 128">' +
        '<circle class="ring-bg" cx="64" cy="64" r="54"></circle>' +
        '<circle class="ring-fg" id="result-ring-fg" cx="64" cy="64" r="54" stroke="' + tone + '"></circle></svg>' +
        '<div class="ring-inner"><span class="grade-letter" style="color:' + tone + '">' + esc(grade) + "</span>" +
        '<span class="grade-score">' + total + " / 100</span></div></div>" +
        '<div class="result-info"><div class="result-badges">' +
        '<span class="result-pass' + (passed ? "" : " fail") + '">' + (passed ? "✓ 通过 · 达到 80 分线" : "未通过 · 差 " + Math.max(0, PASS_LINE - total) + " 分") + "</span>" +
        (seeded ? '<span class="pill">历史演示数据</span>' : "") +
        (r.judge_available ? "" : '<span class="pill">规则评分</span>') +
        "</div><h2>" + esc(lv.name) + " · " + esc(grade) + " 级</h2>" +
        '<p class="lvl-line">' + esc(lv.tier) + " · " + esc(lv.difficulty) + " · " + (r.turns || 0) + " 回合 · 平均首响 " +
        (r.avg_latency_s == null ? "—" : r.avg_latency_s + " 秒") +
        (r.duration_s ? " · 用时 " + formatDuration(r.duration_s) : "") + "</p>" +
        '<p class="summary">' + esc(r.summary || "本局已完成评分。") + "</p></div></div>" +
        (dimHtml ? '<div class="modal-section"><h4>能力维度</h4><div class="dim-list">' + dimHtml + "</div></div>" : "") +
        objHtml +
        '<div class="result-grid"><div class="modal-section"><h4>教练点评</h4><div class="feedback-list">' + feedbackHtml + "</div></div>" +
        '<div class="modal-section"><h4>做得好的地方</h4><div class="feedback-list">' + strengthHtml + "</div></div></div>" +
        rewardHtml +
        '<p class="judge-note">' + esc(judgeNote) + "</p>" +
        actionsHtml,
      { wide: true }
    );

    const fg = $("#result-ring-fg");
    if (fg) {
      setTimeout(function () {
        fg.style.strokeDashoffset = String(RING_LEN * (1 - total / 100));
      }, 60);
    }
    $$(".dim-row .bar i").forEach(function (el, i) {
      setTimeout(function () {
        el.style.width = (el.dataset.width || 0) + "%";
      }, 90 + i * 80);
    });
  }

  /* ---------------- 数据看板 ---------------- */

  async function loadAdmin(force) {
    if (S.adminLoading) return;
    if (S.admin && !force) {
      renderAdmin();
      return;
    }
    S.adminLoading = true;
    try {
      S.admin = await api("/admin/overview");
      S.adminLoading = false;
      if (S.view === "admin") renderAdmin();
    } catch (err) {
      S.adminLoading = false;
      toast(err.message || "加载看板失败", "error");
    }
  }

  function kpiCard(icon, label, value, unit, foot, tone, footGood) {
    return (
      '<div class="kpi-card" style="--kpi-tone:' + tone + '">' +
      '<span class="kpi-icon">' + icon + "</span><span>" + esc(label) + "</span>" +
      "<strong>" + esc(value) + (unit ? "<small>" + esc(unit) + "</small>" : "") + "</strong>" +
      '<span class="foot' + (footGood ? " good" : "") + '">' + esc(foot) + "</span></div>"
    );
  }

  function renderAdmin() {
    const data = S.admin;
    const box = $("#admin-content");
    if (!data) {
      box.innerHTML = '<div class="panel recent-panel"><div class="recent-empty">正在加载看板数据…</div></div>';
      return;
    }
    const k = data.kpis || {};
    const trend = data.trend || [];
    const radar = data.radar || [];
    const weak = data.weak || [];
    const levelDist = data.level_distribution || [];
    const leaderboard = data.leaderboard || [];
    const recent = data.recent_runs || [];
    const roi = data.roi || {};
    const assumptions = roi.assumptions || {};

    if (!S.roi) {
      S.roi = {
        runs: 300,
        minutes: Math.round(Number(assumptions.ojt_minutes_per_run) || 25),
        rate: Math.round(Number(assumptions.mentor_hourly_cny) || 120),
        hires: Math.max(1, Math.round(Number(assumptions.new_hire_count) || k.trainees || 1)),
      };
    }

    const demoNote = k.seeded_runs
      ? '<span class="demo-note">● 含 ' + k.seeded_runs + " 条演示历史数据</span>"
      : "";
    const tenantName = (data.tenant && data.tenant.name) || "企业租户";

    const kpisHtml =
      kpiCard("🎯", "累计训练局数", fmtInt(k.runs), "局", "其中 " + fmtInt(k.seeded_runs) + " 局为演示数据", "#37e1ff") +
      kpiCard("👥", "在训学员", fmtInt(k.trainees), "人", "覆盖 " + fmtInt(k.trainees) + " 份训练档案", "#8a7dff") +
      kpiCard("🏆", "通关率", Math.round((Number(k.pass_rate) || 0) * 100), "%", "通过线 80 分", "#3fe0a7", true) +
      kpiCard("📊", "平均得分", fmtOne(k.avg_score), "分", "五维加权总分", "#ffc857") +
      kpiCard("⚡", "平均首响", fmtOne(k.avg_latency_s), "秒", "目标 ≤ 40 秒", "#6aa8ff") +
      kpiCard("💰", "累计节省成本", fmtCompact(k.cost_saved_cny), "元", "约 " + fmtOne(k.hours_saved) + " 小时带教", "#ff7ac3");

    const weakHtml = weak.length
      ? weak
          .map(function (w) {
            return (
              '<div class="weak-row"><span>' + esc(w.label) + '</span><div class="bar"><i style="width:' +
              Math.max(2, Number(w.value) || 0) + '%"></i></div><b>' + fmtOne(w.value) + "</b>" +
              '<span class="gap">距满分 ' + fmtOne(w.gap) + " 分 · 权重 " + Math.round((Number(w.weight) || 0) * 100) + "%</span></div>"
            );
          })
          .join("")
      : '<p class="muted">暂无可分析的能力数据</p>';

    const distHtml = levelDist
      .map(function (row) {
        const metaLv = metaLevelById(row.level_id);
        const color = (metaLv && metaLv.tier_color) || "#37e1ff";
        const rate = Math.round((Number(row.pass_rate) || 0) * 100);
        return (
          '<div class="dist-row" style="--dist-tone:' + esc(color) + '"><span class="nm"><i style="background:' + esc(color) + '"></i>' +
          esc(row.name) + '</span><div class="bar"><i style="width:' + rate + '%"></i></div>' +
          '<span class="rate">' + rate + '%</span><span class="att">' + (row.attempts || 0) + " 局</span></div>"
        );
      })
      .join("");

    const lbHtml = leaderboard.length
      ? leaderboard
          .map(function (t, i) {
            return (
              '<div class="lb-row"><span class="rank-no">' + (i + 1) + '</span><span class="avatar">' + esc(t.avatar) +
              '</span><div class="who"><b>' + esc(t.name) + "</b><small>" + (t.passed_levels || 0) + "/" +
              ((S.meta && S.meta.levels) ? S.meta.levels.length : 8) + " 关 · 均分 " + fmtOne(t.avg_score) + "</small></div>" +
              '<span class="rank-chip" style="--tone:' + esc(t.rank_color || "#37e1ff") + '">' + esc(t.rank) + "</span>" +
              '<span class="xp">' + fmtInt(t.xp) + "<small>XP</small></span></div>"
            );
          })
          .join("")
      : '<p class="muted">暂无学员数据</p>';

    const recentHtml = recent.length
      ? '<table class="table"><thead><tr><th>学员</th><th>关卡</th><th>结果</th><th>得分</th><th>首响</th><th>完成时间</th></tr></thead><tbody>' +
        recent
          .map(function (r) {
            return (
              '<tr data-act="view-run" data-run="' + esc(r.id) + '" style="cursor:pointer">' +
              '<td><div class="nm"><span class="avatar">' + esc(r.trainee_avatar) + "</span>" + esc(r.trainee_name) + "</div></td>" +
              "<td>" + esc(r.level_name) + "</td>" +
              '<td><span class="status-chip ' + (r.status === "passed" ? "passed" : "failed") + '">' +
              (r.status === "passed" ? "通过" : "未通过") + "</span></td>" +
              '<td class="score">' + (r.total_score == null ? "—" : r.total_score) + "</td>" +
              "<td>" + fmtOne(r.avg_latency_s) + "s</td>" +
              '<td class="time">' + fmtShortDateTime(r.finished_at) + "</td></tr>"
            );
          })
          .join("") +
        "</tbody></table>"
      : '<p class="muted">暂无训练记录</p>';

    const roiDefaults = S.roi;
    const formula = roi.formula || "节省金额 = 训练局数 × 每局替代带教分钟 ÷ 60 × 带教时薪";
    const onboarding = assumptions.onboarding_days_saved || 9;

    box.innerHTML =
      '<div class="admin-head"><div><p class="eyebrow">Admin Insights · 管理驾驶舱</p>' +
      '<h1>数据看板 <span class="muted">' + esc(tenantName) + "</span></h1>" +
      '<p class="sub">生成于 ' + esc(fmtDateTime(data.generated_at)) + " · 通过率、能力雷达与 ROI 自动汇总</p></div>" +
      '<div class="admin-tools">' + demoNote +
      '<button class="btn ghost small" data-act="refresh-admin">↻ 刷新数据</button></div></div>' +
      '<div class="kpi-grid">' + kpisHtml + "</div>" +
      '<div class="dash-grid">' +
      '<div class="panel dash-card span-7"><div class="card-head"><div><h3>训练趋势</h3><p class="sub">近 14 天 · 局数与平均分</p></div>' +
      '<div class="chart-legend"><span><i></i>训练局数</span><span><i class="line"></i>平均分（右轴）</span></div></div>' +
      '<div class="chart-wrap" id="trend-chart"></div></div>' +
      '<div class="panel dash-card span-5"><div class="card-head"><div><h3>团队能力雷达</h3><p class="sub">全员平均 · 五维评分</p></div>' +
      '<span class="aside">满分 100<br>权重见内圈</span></div><div class="chart-wrap" id="team-radar"></div></div>' +
      '<div class="panel dash-card span-4"><div class="card-head"><div><h3>能力短板 TOP 3</h3><p class="sub">优先安排补训方向</p></div></div>' +
      '<div class="weak-list">' + weakHtml + "</div></div>" +
      '<div class="panel dash-card span-8"><div class="card-head"><div><h3>关卡通关分布</h3><p class="sub">每一关的通过率与训练量</p></div>' +
      '<span class="aside">通过率 · 局数</span></div><div class="level-dist">' + distHtml + "</div></div>" +
      '<div class="panel dash-card span-5"><div class="card-head"><div><h3>学员排行榜</h3><p class="sub">按 XP 段位排序</p></div>' +
      '<span class="aside">XP</span></div><div class="leaderboard">' + lbHtml + "</div></div>" +
      '<div class="panel dash-card span-7"><div class="card-head"><div><h3>最近训练记录</h3><p class="sub">点击任意一局查看复盘</p></div></div>' +
      recentHtml + "</div>" +
      '<div class="panel dash-card roi-card span-12"><div class="card-head"><div><h3>带教成本节省测算</h3>' +
      '<p class="sub">拖动参数，估算 AI 陪练替代人工带教的规模效益</p></div><span class="pill">模拟测算</span></div>' +
      '<div class="roi-layout"><div class="roi-controls">' +
      '<div class="roi-control"><div class="rl"><span>每月训练局数</span><b><span id="roi-runs-val">' + roiDefaults.runs + "</span> 局</b></div>" +
      '<input id="roi-runs" type="range" data-roi="runs" min="50" max="2000" step="25" value="' + roiDefaults.runs + '"></div>' +
      '<div class="roi-control"><div class="rl"><span>每局替代带教分钟</span><b><span id="roi-minutes-val">' + roiDefaults.minutes + "</span> 分钟</b></div>" +
      '<input id="roi-minutes" type="range" data-roi="minutes" min="5" max="60" step="5" value="' + roiDefaults.minutes + '"></div>' +
      '<div class="roi-control"><div class="rl"><span>带教时薪</span><b><span id="roi-rate-val">' + roiDefaults.rate + "</span> 元/时</b></div>" +
      '<input id="roi-rate" type="range" data-roi="rate" min="50" max="300" step="10" value="' + roiDefaults.rate + '"></div>' +
      '<div class="roi-control"><div class="rl"><span>新员工人数</span><b><span id="roi-hires-val">' + roiDefaults.hires + "</span> 人</b></div>" +
      '<input id="roi-hires" type="range" data-roi="hires" min="1" max="50" step="1" value="' + roiDefaults.hires + '"></div>' +
      "</div><div class=\"roi-side\"><div class=\"roi-result\">" +
      '<div class="f"><span>月度节省金额</span><b id="roi-monthly">—</b></div>' +
      '<div class="f"><span>年度节省金额</span><b id="roi-annual">—</b></div>' +
      '<div class="f"><span>每月释放带教工时</span><b id="roi-hours">—</b></div>' +
      '<div class="f"><span>新员工人均年省</span><b id="roi-perhire">—</b></div></div>' +
      '<p class="roi-note" id="roi-note"></p>' +
      '<div class="roi-formula">' + esc(formula) + "；新员工上手周期按缩短 " + onboarding + " 天估算。</div>" +
      "</div></div></div>" +
      "</div>" +
      '<p class="dash-foot">GameMaster AI · 数据来自本机 SQLite · 演示数据仅用于产品展示</p>';

    GMCharts.trend($("#trend-chart"), trend);
    GMCharts.radar($("#team-radar"), radar);
    updateRoiOutputs();
  }

  function updateRoiOutputs() {
    if (!S.roi) return;
    const runsEl = $("#roi-runs");
    if (!runsEl) return;
    const minutesEl = $("#roi-minutes");
    const rateEl = $("#roi-rate");
    const hiresEl = $("#roi-hires");
    S.roi = {
      runs: Number(runsEl.value) || 0,
      minutes: Number(minutesEl.value) || 0,
      rate: Number(rateEl.value) || 0,
      hires: Math.max(1, Number(hiresEl.value) || 1),
    };
    const hours = (S.roi.runs * S.roi.minutes) / 60;
    const monthly = hours * S.roi.rate;
    const annual = monthly * 12;
    const perHire = annual / S.roi.hires;

    const setText = function (id, value) {
      const el = $("#" + id);
      if (el) el.textContent = value;
    };
    setText("roi-runs-val", S.roi.runs);
    setText("roi-minutes-val", S.roi.minutes);
    setText("roi-rate-val", S.roi.rate);
    setText("roi-hires-val", S.roi.hires);
    setText("roi-monthly", "¥" + fmtInt(monthly));
    setText("roi-annual", "¥" + fmtInt(annual));
    setText("roi-hours", fmtOne(hours) + " h");
    setText("roi-perhire", "¥" + fmtInt(perHire));
    setText(
      "roi-note",
      "按每月 " + S.roi.runs + " 局、每局替代 " + S.roi.minutes + " 分钟带教、时薪 ¥" +
        S.roi.rate + " 计算，金额按 " + S.roi.hires + " 名新员工分摊。此为测算模型，非真实财务数据。"
    );
  }

  /* ---------------- 新建学员 ---------------- */

  function openNewTraineeModal() {
    closeTraineeMenu();
    openModal(
      '<button class="modal-close" data-act="close-modal" aria-label="关闭">✕</button>' +
        '<form id="new-trainee-form" autocomplete="off">' +
        '<div class="modal-head"><p class="eyebrow">New Trainee · 新建档案</p><h2>创建学员</h2>' +
        "<p>输入昵称后即可从青铜关卡开始第一场 AI 实战对练。</p></div>" +
        '<div class="field"><label for="new-trainee-name">学员昵称</label>' +
        '<input id="new-trainee-name" name="name" maxlength="20" required placeholder="例如：林小满" /></div>' +
        '<div class="modal-actions"><button type="button" class="btn ghost" data-act="close-modal">取消</button>' +
        '<button type="submit" class="btn primary">创建并进入</button></div></form>'
    );
    setTimeout(function () {
      const input = $("#new-trainee-name");
      if (input) input.focus();
    }, 160);
  }

  async function createTrainee(form) {
    const input = $("#new-trainee-name");
    const name = input ? input.value.trim() : "";
    if (!name) {
      toast("请输入学员昵称", "warn");
      return;
    }
    showLoading("正在创建学员档案…");
    try {
      const res = await api("/trainees", { method: "POST", body: { name: name } });
      S.admin = null;
      hideLoading();
      closeModal();
      await loadTrainees();
      await selectTrainee(res.trainee.id);
      setView("lobby");
      toast("已创建学员「" + name + "」，点击下一关开始对练", "success");
    } catch (err) {
      hideLoading();
      toast(err.message || "创建学员失败", "error");
    }
  }

  async function switchTrainee(id) {
    closeTraineeMenu();
    if (!id || id === S.traineeId) return;
    const doSwitch = async function () {
      closeModal();
      const wasBattle = S.view === "battle";
      await selectTrainee(id);
      if (wasBattle) setView("lobby");
      const trainee = S.trainees.find((t) => t.id === id);
      if (trainee) toast("已切换到 " + trainee.name, "info");
    };
    if (S.run && S.run.run.status === "active" && S.run.trainee.id !== id) {
      openConfirm({
        title: "切换学员？",
        body: "当前对练尚未结束，切换后返回大厅；这一局仍保留在「实战对练」标签中，可随时继续。",
        confirmText: "切换学员",
        cancelText: "留在本局",
        onConfirm: doSwitch,
      });
      return;
    }
    doSwitch();
  }

  /* ---------------- 事件绑定 ---------------- */

  function bindEvents() {
    $("#brand-home").addEventListener("click", function (e) {
      e.preventDefault();
      setView("lobby");
    });

    $("#nav-tabs").addEventListener("click", function (e) {
      const tab = e.target.closest(".tab");
      if (!tab) return;
      setView(tab.dataset.view);
    });

    $("#trainee-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      toggleTraineeMenu();
    });

    document.addEventListener("click", function (e) {
      if (!e.target.closest(".top-actions")) closeTraineeMenu();
      if (e.target.classList.contains("modal-overlay")) {
        closeModal();
        return;
      }
      const el = e.target.closest("[data-act]");
      if (!el) return;
      const act = el.dataset.act;
      if (act === "close-modal") {
        closeModal();
        return;
      }
      if (act === "confirm-yes") {
        const cb = S.confirmCb;
        S.confirmCb = null;
        closeModal();
        if (cb) cb();
        return;
      }
      handleAction(act, el);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        closeModal();
        closeTraineeMenu();
      }
    });

    $("#send-btn").addEventListener("click", sendMessage);
    $("#hint-btn").addEventListener("click", requestHint);

    $("#chat-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        if (e.isComposing || e.keyCode === 229) return; // 中文输入法组合中
        e.preventDefault();
        sendMessage();
      }
    });
    $("#chat-input").addEventListener("input", function (e) {
      autoGrow(e.target);
    });

    $("#admin-content").addEventListener("input", function (e) {
      if (e.target && e.target.matches && e.target.matches("input[data-roi]")) {
        updateRoiOutputs();
      }
    });

    document.addEventListener("submit", function (e) {
      if (e.target && e.target.id === "new-trainee-form") {
        e.preventDefault();
        createTrainee(e.target);
      }
    });

    $("#llm-chip").addEventListener("click", function () {
      const ai = (S.run && S.run.ai) || (S.meta && S.meta.llm) || (S.health && S.health.llm);
      if (!ai) {
        toast("正在探测本地模型", "info");
        return;
      }
      if (ai.available) {
        toast("本地模型 " + (ai.model || "") + " 在线 · " + (ai.base_url || ""), "success");
      } else {
        toast("本地模型不可用：" + (ai.error || "请确认 Ollama 已启动") + "，当前使用模板兜底", "warn");
      }
    });
  }

  function handleAction(act, el) {
    switch (act) {
      case "view-admin":
        setView("admin");
        break;
      case "view-battle":
        setView("battle");
        break;
      case "back-lobby":
        setView("lobby");
        toast("本局已保留，可随时从顶部「实战对练」返回", "info");
        break;
      case "brief-level":
        if (el.dataset.locked === "1") {
          toast("请先通过上一关，再挑战本关", "warn");
          return;
        }
        openBriefing(el.dataset.level);
        break;
      case "start-level":
        startRun(el.dataset.level);
        break;
      case "finish":
        openFinishConfirm();
        break;
      case "new-trainee":
        openNewTraineeModal();
        break;
      case "switch-trainee":
        switchTrainee(el.dataset.id);
        break;
      case "view-run":
        openResultForRun(el.dataset.run);
        break;
      case "result-lobby":
        closeModal();
        setView("lobby");
        break;
      case "refresh-admin":
        S.admin = null;
        loadAdmin(true);
        break;
      case "toggle-kb": {
        const item = el.closest(".kb-item");
        if (!item) return;
        const body = $(".kb-body", item);
        const open = item.classList.toggle("open");
        if (body) body.hidden = !open;
        el.setAttribute("aria-expanded", open ? "true" : "false");
        break;
      }
      default:
        break;
    }
  }

  /* ---------------- 启动监听 ---------------- */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
