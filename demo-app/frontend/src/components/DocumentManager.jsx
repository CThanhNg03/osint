import React, { useEffect, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const formatDate = (value) => {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("vi-VN", { hour12: false });
  } catch {
    return value;
  }
};

const DocumentManager = () => {
  const [documents, setDocuments] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [extractingId, setExtractingId] = useState(null);
  const [kgResult, setKgResult] = useState(null);
  const fileInputRef = useRef(null);

  const fetchDocuments = async () => {
    try {
      const resp = await fetch(`${API_URL}/documents`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setDocuments(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Không tải được danh sách tài liệu");
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDetail = async (docId) => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`${API_URL}/documents/${docId}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setSelectedDoc(data);
      setSelectedId(docId);
      setKgResult(null);
    } catch (err) {
      setError(err.message || "Không tải được chi tiết tài liệu");
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const resp = await fetch(`${API_URL}/documents/upload`, {
        method: "POST",
        body: form,
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const doc = await resp.json();
      setDocuments((prev) => [doc, ...prev]);
      setSelectedDoc(doc);
      setSelectedId(doc.id);
      setKgResult(null);
    } catch (err) {
      setError(err.message || "Tải lên thất bại");
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDelete = async (docId) => {
    if (!window.confirm("Xóa tài liệu này?")) return;
    try {
      const resp = await fetch(`${API_URL}/documents/${docId}`, {
        method: "DELETE",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      if (selectedId === docId) {
        setSelectedDoc(null);
        setSelectedId(null);
        setKgResult(null);
      }
    } catch (err) {
      setError(err.message || "Không thể xóa tài liệu");
    }
  };

  const handleExtractKg = async (docId) => {
    setExtractingId(docId);
    setError("");
    try {
      const resp = await fetch(`${API_URL}/documents/${docId}/extract-kg`, {
        method: "POST",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setKgResult(data);
    } catch (err) {
      setError(err.message || "Không thể trích xuất KG");
    } finally {
      setExtractingId(null);
    }
  };

  const pdfMetadata = selectedDoc?.metadata?.pdf_metadata || {};
  const previewUrl = selectedDoc ? `${API_URL}/documents/${selectedDoc.id}/file` : null;

  return (
    <div className="h-full w-full bg-gray-950 text-white p-4 flex flex-col gap-4 overflow-hidden">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">OCR Document Manager</h2>
          <p className="text-sm text-gray-400">
            Tải lên PDF, xem metadata, tóm tắt và trích xuất Knowledge Graph.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => fileInputRef.current?.click()}
            className="px-4 py-2 rounded bg-emerald-600 hover:bg-emerald-500 font-semibold text-sm disabled:opacity-60"
            disabled={uploading}
          >
            {uploading ? "Đang tải..." : "Upload PDF"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={handleUpload}
          />
        </div>
      </div>

      {error && <div className="text-red-400 text-sm">{error}</div>}

      <div className="grid grid-cols-5 gap-4 flex-1 overflow-hidden">
        <div className="col-span-3 bg-gray-900 border border-gray-800 rounded-lg p-3 overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-gray-400 uppercase text-xs border-b border-gray-800">
              <tr>
                <th className="text-left py-2">Tên</th>
                <th className="text-left py-2">Trang</th>
                <th className="text-left py-2">Tóm tắt</th>
                <th className="text-left py-2">Thời gian</th>
                <th className="text-right py-2">Hành động</th>
              </tr>
            </thead>
            <tbody>
              {documents.length === 0 && (
                <tr>
                  <td colSpan={5} className="text-center py-6 text-gray-500">
                    Chưa có tài liệu nào.
                  </td>
                </tr>
              )}
              {documents.map((doc) => (
                <tr
                  key={doc.id}
                  className={`border-b border-gray-850 hover:bg-gray-850 ${
                    selectedId === doc.id ? "bg-gray-850" : ""
                  }`}
                >
                  <td className="py-3">
                    <button
                      type="button"
                      onClick={() => fetchDetail(doc.id)}
                      className="text-left text-indigo-300 hover:text-indigo-100 font-semibold"
                    >
                      {doc.original_name}
                    </button>
                  </td>
                  <td className="py-3">{doc.pages || 0}</td>
                  <td className="py-3 text-gray-300 line-clamp-2">
                    {doc.summary || "-"}
                  </td>
                  <td className="py-3 text-gray-400">{formatDate(doc.created_at)}</td>
                  <td className="py-3 text-right">
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => handleExtractKg(doc.id)}
                        className="px-3 py-1 bg-purple-700 text-xs rounded hover:bg-purple-600 disabled:opacity-50"
                        disabled={extractingId === doc.id}
                      >
                        {extractingId === doc.id ? "Đang trích..." : "Trích KG"}
                      </button>
                      <button
                        onClick={() => handleDelete(doc.id)}
                        className="px-3 py-1 bg-red-700 text-xs rounded hover:bg-red-600"
                      >
                        Xóa
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="col-span-2 bg-gray-900 border border-gray-800 rounded-lg p-4 overflow-auto space-y-4">
          {!selectedDoc && (
            <div className="text-gray-400 text-sm">Chọn hoặc tải lên tài liệu để xem chi tiết.</div>
          )}
          {selectedDoc && (
            <>
              <div>
                <h3 className="text-lg font-semibold">{selectedDoc.original_name}</h3>
                <p className="text-xs text-gray-400">Số trang: {selectedDoc.pages || 0}</p>
                <p className="text-xs text-gray-400">
                  Tải lên: {formatDate(selectedDoc.created_at)}
                </p>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-1 text-indigo-300">Xem nhanh</h4>
                {previewUrl ? (
                  <iframe
                    title="Document preview"
                    src={`${previewUrl}#toolbar=0`}
                    className="w-full h-64 rounded border border-gray-800 bg-gray-950"
                  />
                ) : (
                  <div className="text-sm text-gray-500">Không có bản xem trước.</div>
                )}
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-1 text-indigo-300">Tóm tắt</h4>
                <p className="text-sm text-gray-200 whitespace-pre-wrap">
                  {selectedDoc.summary || "Chưa có tóm tắt."}
                </p>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-1 text-indigo-300">Metadata chính</h4>
                <div className="grid grid-cols-2 gap-3 text-xs text-gray-300 bg-gray-950 border border-gray-800 rounded p-3">
                  <div>
                    <div className="text-gray-400 uppercase text-[10px]">Tác giả</div>
                    <div>{pdfMetadata.Author || "-"}</div>
                  </div>
                  <div>
                    <div className="text-gray-400 uppercase text-[10px]">Người tạo</div>
                    <div>{pdfMetadata.Creator || "-"}</div>
                  </div>
                  <div>
                    <div className="text-gray-400 uppercase text-[10px]">Producer</div>
                    <div>{pdfMetadata.Producer || "-"}</div>
                  </div>
                  <div>
                    <div className="text-gray-400 uppercase text-[10px]">Ngày tạo</div>
                    <div>{pdfMetadata.CreationDate || "-"}</div>
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-1 text-indigo-300">Trích đoạn</h4>
                <p className="text-sm text-gray-300 whitespace-pre-wrap max-h-40 overflow-auto">
                  {selectedDoc.text_excerpt || "Không có nội dung."}
                </p>
              </div>

              <div>
                <h4 className="text-sm font-semibold mb-1 text-indigo-300">Metadata</h4>
                <pre className="bg-gray-950 border border-gray-800 rounded p-3 text-xs overflow-auto">
                  {JSON.stringify(selectedDoc.metadata || {}, null, 2)}
                </pre>
              </div>

              {kgResult && (
                <div>
                  <h4 className="text-sm font-semibold mb-1 text-emerald-300">
                    Knowledge Graph (neo4j:{" "}
                    {kgResult.neo4j_upserted ? "đã cập nhật" : "chưa kết nối"})
                  </h4>
                  <pre className="bg-gray-950 border border-emerald-800/50 rounded p-3 text-xs overflow-auto">
                    {JSON.stringify(kgResult.kg, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}
          {loading && <div className="text-sm text-gray-400">Đang tải chi tiết...</div>}
        </div>
      </div>
    </div>
  );
};

export default DocumentManager;
