import { redirect } from "next/navigation";

export default function InventoryRedirectPage() {
  redirect("/dashboard/pantry");
}
