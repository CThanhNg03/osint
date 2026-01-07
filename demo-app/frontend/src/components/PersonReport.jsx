import React, { useEffect, useMemo, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const normalizeLines = (value) => {
  if (!value) return [];
  const source = Array.isArray(value) ? value : String(value).split(/\n+/);
  return source
    .map((line) => line.replace(/^-+\s*/, "").trim())
    .filter(Boolean);
};

const truncateText = (text, limit = 220) => {
  if (!text) return "";
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 1).trim()}…`;
};

const renderSummaryBlock = (value) => {
  const items = normalizeLines(value);
  if (items.length === 0) {
    return <p className="text-sm text-gray-400">Không có dữ liệu.</p>;
  }

  const paragraph = truncateText(items[0], 320);
  const bullets = items.slice(1, 5).map((item) => truncateText(item, 200));

  return (
    <div className="space-y-2 text-sm text-gray-100">
      {paragraph && <p className="leading-relaxed">{paragraph}</p>}
      {bullets.length > 0 && (
        <ul className="list-disc pl-5 space-y-1 text-sm text-gray-100">
          {bullets.map((item, idx) => (
            <li key={idx} className="leading-snug">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const TopMeta = ({ person, updatedAt }) => {
  const detail = person?.properties || {};
  return (
    <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 border border-slate-700 rounded-xl p-6 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm uppercase tracking-[0.3em] text-amber-400 font-semibold">
            Báo Cáo: Quản Trị Điều Hành
          </p>
          <h2 className="text-2xl font-bold text-white mt-1">
            {person?.name || detail?.name || "Đối tượng"}
          </h2>
          <p className="text-sm text-slate-300">
            Nhóm: {person?.type || detail?.role || "Person"}{" "}
            {detail?.role ? `• Vai trò: ${detail.role}` : ""}
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-300">
          <div className="text-right">
            <p className="uppercase tracking-widest text-slate-400">
              High-priority executive intelligence
            </p>
            <p className="text-sm text-white">
              Thời gian xuất bản: {updatedAt}
            </p>
          </div>
          <div className="px-3 py-2 bg-red-900/40 text-red-300 border border-red-600 rounded-lg text-center">
            <p className="text-[11px] uppercase tracking-wide">Độ khẩn</p>
            <p className="text-lg font-bold">Cao</p>
          </div>
        </div>
      </div>
    </div>
  );
};

const PersonReport = ({ target, onBack }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState(null);

  const identifier = useMemo(() => {
    if (!target) return null;
    return (
      target.identifier ||
      target.person_id ||
      target?.node?.properties?.person_id ||
      target?.node?.properties?.name ||
      target?.node?.id ||
      target?.name ||
      null
    );
  }, [target]);

  const displayName = target?.name || target?.node?.properties?.name || identifier;

  useEffect(() => {
    if (!identifier) {
      setData(null);
      setError("Chưa chọn đối tượng để tạo báo cáo.");
      setLoading(false);
      return;
    }
    let active = true;
    (async () => {
      setLoading(true);
      setError("");
      try {
        const resp = await fetch(
          `${API_URL}/kg/person-analysis?node_id=${encodeURIComponent(identifier)}`
        );
        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`);
        }
        const payload = await resp.json();
        if (!active) return;
        setData(payload);
      } catch (err) {
        if (!active) return;
        setError(err.message || "Không thể tải báo cáo");
        setData(null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [identifier]);

  const updatedAt = useMemo(() => {
    return new Date().toLocaleString("vi-VN", {
      hour12: false,
    });
  }, [data]);

  const sectionClass =
    "rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-inner flex flex-col gap-3";

  return (
    <div className="h-full w-full bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white overflow-auto p-6 space-y-5">
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="px-4 py-2 text-sm font-semibold bg-slate-800 hover:bg-slate-700 rounded-lg border border-slate-700"
        >
          ← Quay lại KG
        </button>
        <div className="text-right text-sm text-slate-400">
          <p>Mã đối tượng: {identifier || "N/A"}</p>
          <p>Lần xem gần nhất: {updatedAt}</p>
        </div>
      </div>

      <TopMeta person={data?.person || target?.node} updatedAt={updatedAt} />

      {loading && (
        <div className="text-center text-slate-300 py-10">Đang tổng hợp báo cáo...</div>
      )}
      {error && (
        <div className="text-center text-red-400 py-6">
          {error}. Vui lòng thử lại hoặc kiểm tra kết nối Neo4j.
        </div>
      )}
      {!loading && !error && data && (
        <>
          <div className="grid lg:grid-cols-2 gap-4">
            <section className={`${sectionClass} border-l-4 border-l-amber-500`}>
              <header>
                <p className="text-xs uppercase tracking-widest text-amber-300">
                  Tóm tắt hành động gần đây
                </p>
                <h3 className="text-xl font-bold text-white">
                  {displayName || "Đối tượng"}
                </h3>
                <p className="text-xs text-slate-400">Situation Summary</p>
              </header>
              {renderSummaryBlock(data?.report?.tom_tat_hanh_dong)}
              <div className="text-[11px] text-slate-500 uppercase tracking-widest">
                Nguồn: KG nội bộ + /kg/person-analysis
              </div>
            </section>

            <section className={`${sectionClass} border-l-4 border-l-sky-500`}>
              <header>
                <p className="text-xs uppercase tracking-widest text-sky-300">
                  Hồ sơ đối tượng (Person DB)
                </p>
                <h3 className="text-xl font-bold text-white">Target Profile</h3>
                <p className="text-xs text-slate-400">Threat & Social Graph</p>
              </header>
              {renderSummaryBlock(data?.report?.ho_so_doi_tuong)}
              <div className="mt-3">
                <p className="text-xs uppercase text-slate-400 mb-1">
                  Liên hệ cấp 1 nổi bật
                </p>
                <div className="flex flex-wrap gap-2">
                  {(data?.level1_nodes || []).slice(0, 4).map((n) => (
                    <div
                      key={`${n.node?.id}-${n.relationship_id}`}
                      className="px-3 py-2 bg-slate-800/80 rounded-lg border border-slate-700 text-xs"
                    >
                      <p className="font-semibold text-white">
                        {n.node?.display_name || n.node?.properties?.name || "Ẩn danh"}
                      </p>
                      <p className="text-slate-400">{n.relationship || "Liên hệ"}</p>
                    </div>
                  ))}
                  {(data?.level1_nodes || []).length === 0 && (
                    <p className="text-xs text-slate-500">Chưa có dữ liệu.</p>
                  )}
                </div>
              </div>
            </section>
          </div>

          <div className="grid lg:grid-cols-2 gap-4">
            <section className={`${sectionClass} border-l-4 border-l-purple-500`}>
              <header>
                <p className="text-xs uppercase tracking-widest text-purple-300">
                  Đánh giá tác động
                </p>
                <h3 className="text-xl font-bold text-white">
                  Impact Assessment
                </h3>
                <p className="text-xs text-slate-400">
                  Economic / Political / Social
                </p>
              </header>
              {renderSummaryBlock(data?.report?.danh_gia_tac_dong)}
              <div className="mt-3 text-xs text-slate-400">
                Độ phủ mạng cấp 2: {(data?.level2_nodes || []).length} đối tượng liên quan.
              </div>
            </section>

            <section className={`${sectionClass} border-l-4 border-l-emerald-500`}>
              <header>
                <p className="text-xs uppercase tracking-widest text-emerald-300">
                  Khuyến nghị hành động
                </p>
                <h3 className="text-xl font-bold text-white">
                  Strategic Recommendations
                </h3>
              </header>
              {renderSummaryBlock(data?.report?.khuyen_nghi)}
              <div className="mt-3 text-xs text-slate-400">
                Ghi chú: Ưu tiên các hoạt động có thể triển khai trong 24-48 giờ.
              </div>
            </section>
          </div>
        </>
      )}
    </div>
  );
};

export default PersonReport;
