import { redirect } from "next/navigation";

export default function VideosRedirect() {
  redirect("/media?tab=videos");
}
