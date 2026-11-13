// Haber fotoğrafını bültene almak için görsel aktarıcı (tarayıcının CORS engelini aşar). GET ?u=<görsel adresi>
module.exports = async (req, res) => {
  const u = String((req.query && req.query.u) || "");
  if (!/^https?:\/\//i.test(u)) { res.status(400).send("u"); return; }
  try {
    const r = await fetch(u, { headers: { "User-Agent": "Mozilla/5.0 (compatible; TaskentTicaretBot/1.0)" }, signal: AbortSignal.timeout(8000) });
    const type = r.headers.get("content-type") || "";
    if (!r.ok || !type.startsWith("image/")) { res.status(502).send("görsel alınamadı"); return; }
    const buf = Buffer.from(await r.arrayBuffer());
    if (buf.length > 8 * 1048576) { res.status(413).send("büyük"); return; }
    res.setHeader("Content-Type", type); res.setHeader("Cache-Control", "public, max-age=86400");
    res.status(200).send(buf);
  } catch (e) { res.status(502).send("görsel alınamadı"); }
};
