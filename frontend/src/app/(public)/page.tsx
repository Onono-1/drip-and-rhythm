import { CinematicHomepage } from "@/features/public/cinematic-homepage";
import { fetchPublicEventServer } from "@/lib/server-api";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const event = await fetchPublicEventServer();
  return <CinematicHomepage event={event} />;
}
