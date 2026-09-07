import { redirect } from "next/navigation";
import { HomeFlow } from "@/components/home/home-flow";
import { env } from "@/lib/env";

export default function Home() {
  // D6: flips the root route to the coming-soon page ahead of launch
  // day without a separate deploy — see NEXT_PUBLIC_COMING_SOON.
  if (env.comingSoon) {
    redirect("/coming-soon");
  }
  return <HomeFlow />;
}
