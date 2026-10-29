import { connection } from "next/server";
import Haven from "./ui";
export default async function Page() {
  await connection();
  return <Haven />;
}
