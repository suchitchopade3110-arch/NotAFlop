import { ImageResponse } from "next/og";
import { fetchShareCard } from "@/lib/api/server";

export const runtime = "edge";
export const alt = "NotAFlop verdict";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const TONE_COLOR: Record<string, string> = { go: "#3fae72", pivot: "#e08a3c", "no-go": "#c9524a" };

export default async function OpengraphImage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const card = await fetchShareCard(token);

  const verdict = card?.verdict ?? "no-go";
  const color = TONE_COLOR[verdict] ?? TONE_COLOR["no-go"];
  const score = card?.raw_score ?? 0;
  const keyword = card?.keyword || "A startup idea";
  const reasons = card?.top_reasons.slice(0, 2) ?? [];

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "#0a0a0b",
          color: "#f3f1ea",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 220,
              height: 220,
              borderRadius: "50%",
              border: `16px solid ${color}`,
              fontSize: 88,
              fontWeight: 700,
            }}
          >
            {score}
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 32, color: "#a9a6a0", letterSpacing: 4, textTransform: "uppercase" }}>
              NotAFlop verdict
            </div>
            <div style={{ fontSize: 72, fontWeight: 700, color, marginTop: 8 }}>
              {verdict === "no-go" ? "No-Go" : verdict === "pivot" ? "Pivot" : "Go"}
            </div>
            <div style={{ fontSize: 40, marginTop: 12, maxWidth: 760 }}>{keyword}</div>
          </div>
        </div>
        {reasons.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", marginTop: 48, gap: 12 }}>
            {reasons.map((reason) => (
              <div key={reason} style={{ fontSize: 30, color: "#a9a6a0" }}>
                {reason}
              </div>
            ))}
          </div>
        )}
      </div>
    ),
    { ...size },
  );
}
