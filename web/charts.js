/* ==========================================================
   GameMaster AI · 纯 SVG 图表
   ----------------------------------------------------------
   不依赖任何图表库：为看板提供 14 天趋势与团队能力雷达。
   所有函数接收 DOM 容器与数据，直接写入 SVG。
   ========================================================== */

(function () {
  "use strict";

  const C = {
    cyan: "#37e1ff",
    blue: "#6aa8ff",
    violet: "#8a7dff",
    green: "#3fe0a7",
    gold: "#ffc857",
    red: "#ff6b81",
    dim: "#61708a",
    muted: "#8fa0b8",
    line: "rgba(126,168,224,0.16)",
  };

  function esc(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function niceMax(value) {
    const v = Math.max(1, value);
    const steps = [4, 6, 8, 10, 15, 20, 30, 50, 80, 100, 200, 500];
    for (const s of steps) {
      if (v <= s) return s;
    }
    return Math.ceil(v / 100) * 100;
  }

  function shortDate(iso) {
    if (!iso) return "";
    const parts = String(iso).split("-");
    return parts.length >= 3 ? parts[1] + "/" + parts[2] : String(iso);
  }

  /* ---------------- 14 天训练趋势 ---------------- */

  function trend(el, data) {
    if (!el) return;
    const rows = Array.isArray(data) ? data : [];
    if (!rows.length) {
      el.innerHTML = '<p class="recent-empty">暂无趋势数据</p>';
      return;
    }

    const W = 780;
    const H = 268;
    const M = { l: 36, r: 34, t: 22, b: 30 };
    const pw = W - M.l - M.r;
    const ph = H - M.t - M.b;
    const n = rows.length;
    const maxRuns = niceMax(Math.max.apply(null, rows.map((r) => r.runs || 0)));
    const slot = pw / n;
    const barW = Math.min(26, slot * 0.44);

    const parts = [];
    parts.push('<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="近 14 天训练局数与平均分趋势">');
    parts.push(
      "<defs>" +
        '<linearGradient id="gmTrendBars" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0%" stop-color="' + C.cyan + '" stop-opacity="0.85"/>' +
        '<stop offset="100%" stop-color="' + C.cyan + '" stop-opacity="0.06"/>' +
        "</linearGradient>" +
        '<linearGradient id="gmTrendArea" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0%" stop-color="' + C.violet + '" stop-opacity="0.22"/>' +
        '<stop offset="100%" stop-color="' + C.violet + '" stop-opacity="0"/>' +
        "</linearGradient>" +
        "</defs>"
    );

    // 横向网格与左轴（局数）
    const gridCount = 4;
    for (let i = 0; i <= gridCount; i++) {
      const y = M.t + (ph * i) / gridCount;
      const runsLabel = Math.round(maxRuns - (maxRuns * i) / gridCount);
      parts.push(
        '<line x1="' + M.l + '" y1="' + y + '" x2="' + (W - M.r) + '" y2="' + y +
          '" stroke="' + C.line + '" stroke-width="1" stroke-dasharray="' + (i === gridCount ? "0" : "3 5") + '"/>'
      );
      parts.push(
        '<text x="' + (M.l - 8) + '" y="' + (y + 3) + '" text-anchor="end" class="chart-axis">' + runsLabel + "</text>"
      );
      const scoreLabel = Math.round(100 - (100 * i) / gridCount);
      parts.push(
        '<text x="' + (W - M.r + 8) + '" y="' + (y + 3) + '" text-anchor="start" class="chart-axis" fill="' +
          C.violet + '" opacity="0.65">' + scoreLabel + "</text>"
      );
    }

    // 柱状：每日局数
    rows.forEach(function (r, i) {
      const x = M.l + slot * i + (slot - barW) / 2;
      const runs = Math.max(0, r.runs || 0);
      const h = maxRuns ? (ph * runs) / maxRuns : 0;
      const y = M.t + ph - h;
      if (runs > 0) {
        parts.push(
          '<rect x="' + x.toFixed(1) + '" y="' + y.toFixed(1) + '" width="' + barW.toFixed(1) + '" height="' +
            Math.max(2, h).toFixed(1) + '" rx="' + Math.min(5, barW / 2).toFixed(1) + '" fill="url(#gmTrendBars)">' +
            "<title>" + esc(r.date) + " · " + runs + " 局 · 通过 " + (r.passed || 0) + "</title></rect>"
        );
        if (runs >= 3 && barW >= 18) {
          parts.push(
            '<text x="' + (x + barW / 2).toFixed(1) + '" y="' + (y - 5).toFixed(1) +
              '" text-anchor="middle" class="chart-axis" fill="' + C.muted + '">' + runs + "</text>"
          );
        }
      }
    });

    // 折线：平均分（无数据日断线）
    const scoreY = (score) => M.t + ph - (Math.max(0, Math.min(100, score)) / 100) * ph;
    const segments = [];
    let current = [];
    rows.forEach(function (r, i) {
      if (r.runs > 0 && Number.isFinite(Number(r.avg_score)) && r.avg_score > 0) {
        current.push({
          x: M.l + slot * i + slot / 2,
          y: scoreY(Number(r.avg_score)),
          r: r,
        });
      } else if (current.length) {
        segments.push(current);
        current = [];
      }
    });
    if (current.length) segments.push(current);

    segments.forEach(function (seg) {
      if (seg.length > 1) {
        const pts = seg.map((p) => p.x.toFixed(1) + "," + p.y.toFixed(1)).join(" ");
        parts.push(
          '<polyline points="' + pts + '" fill="none" stroke="' + C.violet + '" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" opacity="0.9"/>'
        );
        const areaPts =
          seg.map((p) => p.x.toFixed(1) + "," + p.y.toFixed(1)).join(" ") +
          " " + seg[seg.length - 1].x.toFixed(1) + "," + (M.t + ph) +
          " " + seg[0].x.toFixed(1) + "," + (M.t + ph);
        parts.push('<polygon points="' + areaPts + '" fill="url(#gmTrendArea)" stroke="none"/>');
      }
      seg.forEach(function (p) {
        parts.push(
          '<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="3.2" fill="' + C.violet +
            '" stroke="#0b111b" stroke-width="1.5"><title>' + esc(p.r.date) + " · 平均分 " + p.r.avg_score + "</title></circle>"
        );
      });
    });

    // 横轴日期
    rows.forEach(function (r, i) {
      if (i % 2 !== 0 && i !== n - 1) return;
      const x = M.l + slot * i + slot / 2;
      parts.push(
        '<text x="' + x.toFixed(1) + '" y="' + (H - 9) + '" text-anchor="middle" class="chart-axis">' +
          esc(shortDate(r.date)) + "</text>"
      );
    });

    parts.push("</svg>");
    el.innerHTML = parts.join("");
  }

  /* ---------------- 团队能力雷达 ---------------- */

  function radar(el, items) {
    if (!el) return;
    const rows = Array.isArray(items) ? items.filter(Boolean) : [];
    if (!rows.length) {
      el.innerHTML = '<p class="recent-empty">暂无能力数据</p>';
      return;
    }

    const W = 460;
    const H = 376;
    const cx = W / 2;
    const cy = 182;
    const R = 116;
    const n = rows.length;
    const start = -Math.PI / 2;

    const point = (index, value) => {
      const angle = start + (Math.PI * 2 * index) / n;
      const rr = R * Math.max(0, Math.min(1, value / 100));
      return { x: cx + rr * Math.cos(angle), y: cy + rr * Math.sin(angle), angle: angle };
    };

    const parts = [];
    parts.push('<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="团队五维能力雷达图">');
    parts.push(
      "<defs>" +
        '<linearGradient id="gmRadarFill" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0%" stop-color="' + C.cyan + '" stop-opacity="0.34"/>' +
        '<stop offset="100%" stop-color="' + C.violet + '" stop-opacity="0.10"/>' +
        "</linearGradient>" +
        "</defs>"
    );

    // 同心环
    [0.25, 0.5, 0.75, 1].forEach(function (ratio) {
      const pts = [];
      for (let i = 0; i < n; i++) {
        const p = point(i, 100 * ratio);
        pts.push(p.x.toFixed(1) + "," + p.y.toFixed(1));
      }
      parts.push(
        '<polygon points="' + pts.join(" ") + '" fill="none" stroke="' + C.line +
          '" stroke-width="' + (ratio === 1 ? 1.2 : 0.8) + '"/>'
      );
    });

    // 轴线
    rows.forEach(function (_, i) {
      const p = point(i, 100);
      parts.push(
        '<line x1="' + cx + '" y1="' + cy + '" x2="' + p.x.toFixed(1) + '" y2="' + p.y.toFixed(1) +
          '" stroke="' + C.line + '" stroke-width="0.8"/>'
      );
    });

    // 数值多边形
    const valuePts = [];
    rows.forEach(function (row, i) {
      const p = point(i, Number(row.value) || 0);
      valuePts.push(p.x.toFixed(1) + "," + p.y.toFixed(1));
    });
    parts.push(
      '<polygon points="' + valuePts.join(" ") + '" fill="url(#gmRadarFill)" stroke="' + C.cyan +
        '" stroke-width="1.6" stroke-linejoin="round"/>'
    );

    rows.forEach(function (row, i) {
      const value = Number(row.value) || 0;
      const p = point(i, value);
      parts.push(
        '<circle cx="' + p.x.toFixed(1) + '" cy="' + p.y.toFixed(1) + '" r="3.6" fill="' + C.cyan +
          '" stroke="#0b111b" stroke-width="1.5"><title>' + esc(row.label) + " " + value + " 分</title></circle>"
      );

      const lp = point(i, 100);
      const lx = cx + (lp.x - cx) * 1.27;
      const ly = cy + (lp.y - cy) * 1.27;
      const cos = Math.cos(lp.angle);
      let anchor = "middle";
      if (cos > 0.35) anchor = "start";
      else if (cos < -0.35) anchor = "end";
      parts.push(
        '<text x="' + lx.toFixed(1) + '" y="' + (ly - 2).toFixed(1) + '" text-anchor="' + anchor +
          '" font-size="10.5" fill="' + C.muted + '">' + esc(row.label) + "</text>"
      );
      parts.push(
        '<text x="' + lx.toFixed(1) + '" y="' + (ly + 13).toFixed(1) + '" text-anchor="' + anchor +
          '" font-family="ui-monospace, monospace" font-size="13" font-weight="600" fill="#e9f0ff">' +
          Math.round(value * 10) / 10 +
          '<tspan font-size="9" fill="' + C.dim + '"> / 100</tspan></text>'
      );
    });

    // 中心刻度 + 底部说明（贴近画布底边，避免压住下方维度标签）
    parts.push(
      '<circle cx="' + cx + '" cy="' + cy + '" r="2" fill="' + C.dim + '"/>' +
        '<text x="' + cx + '" y="' + (H - 8) + '" text-anchor="middle" font-size="8.5" fill="' + C.dim +
        '" letter-spacing="1.5">GROUP AVERAGE · 5 DIMENSIONS</text>'
    );

    parts.push("</svg>");
    el.innerHTML = parts.join("");
  }

  window.GMCharts = { trend: trend, radar: radar };
})();
