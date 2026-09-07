const SOURCE_LABELS: Record<string, string> = {
  google_trends: "Google Trends",
  reddit: "Reddit",
  hacker_news: "Hacker News",
  product_hunt: "Product Hunt",
  wellfound: "Wellfound",
};

export function sourceLabel(key: string): string {
  return SOURCE_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
