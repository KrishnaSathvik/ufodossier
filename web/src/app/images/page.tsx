import { redirect } from "next/navigation";

export default function ImagesRedirect() {
  redirect("/media?tab=images");
}
