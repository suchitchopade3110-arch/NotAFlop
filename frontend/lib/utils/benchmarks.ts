/**
 * C5: "Benchmark the rejection against a well-known historical
 * failure." This list is editorial framing over public knowledge, not
 * a claim of provable similarity — picked deterministically from the
 * idea's keyword (falling back to its share token) so the same idea
 * always benchmarks against the same case, rather than reshuffling on
 * every view.
 */
interface Benchmark {
  name: string;
  year: string;
  lesson: string;
  tags: string[];
}

const BENCHMARKS: Benchmark[] = [
  { name: "Webvan", year: "1999-2001", lesson: "raised huge and built infrastructure years ahead of real demand.", tags: ["grocery", "delivery", "logistics", "shipping"] },
  { name: "Pets.com", year: "1998-2000", lesson: "spent on brand before proving people would actually buy the category online.", tags: ["ecommerce", "retail", "marketplace", "shopping"] },
  { name: "Juicero", year: "2013-2017", lesson: "engineered a hardware solution to a problem people could solve by hand.", tags: ["hardware", "device", "iot", "appliance"] },
  { name: "Quibi", year: "2018-2020", lesson: "had the budget and the talent, but never found the habit it needed people to form.", tags: ["media", "video", "content", "streaming", "entertainment"] },
  { name: "Yik Yak", year: "2013-2017", lesson: "grew fast on novelty and anonymity, then couldn't hold users once the moderation problem caught up.", tags: ["social", "community", "app", "anonymous", "chat"] },
  { name: "Homejoy", year: "2012-2015", lesson: "won on price and lost on the retention a marketplace actually needs to survive.", tags: ["marketplace", "services", "gig", "onDemand", "cleaning"] },
  { name: "Google Glass", year: "2013-2015", lesson: "shipped a real product before the market had a real reason to want it.", tags: ["wearable", "hardware", "ar", "vr", "device"] },
  { name: "Beepi", year: "2013-2017", lesson: "spent aggressively on growth in a business where unit economics never closed.", tags: ["marketplace", "automotive", "ecommerce", "cars"] },
  { name: "Fab.com", year: "2010-2015", lesson: "chased a huge round and a pivot instead of the one segment that was already working.", tags: ["ecommerce", "design", "retail", "marketplace"] },
  { name: "Secret", year: "2014-2015", lesson: "had viral growth with no answer for the abuse that growth attracted.", tags: ["social", "anonymous", "app", "community"] },
];

const GENERAL_POOL = BENCHMARKS;

function hashString(input: string): number {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0;
  }
  return hash;
}

export function benchmarkFor(keyword: string, seed: string): Benchmark {
  const lower = keyword.toLowerCase();
  const matches = BENCHMARKS.filter((b) => b.tags.some((tag) => lower.includes(tag)));
  const pool = matches.length > 0 ? matches : GENERAL_POOL;
  const index = hashString(seed || keyword) % pool.length;
  return pool[index]!;
}
