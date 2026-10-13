import { test, expect, request as apiRequest, type APIRequestContext } from "@playwright/test";
import { Pool } from "pg";
const baseURL=process.env.TEST_BASE_URL!;
const llmURL=process.env.TEST_LLM_URL!;
const db=process.env.AUTH_TEST_DATABASE_URL!;
if (new URL(db).pathname!=="/assistant_rag_test") throw new Error("Dedicated test database required");
const pool=new Pool({connectionString:db,max:2});
const facts="Le lancement du projet Oriole a lieu le 12 décembre 2026 à Lyon. La démonstration dure vingt minutes.";
test.beforeEach(async ({request}) => {
  await pool.query("DELETE FROM auth_rate_limit");
  await pool.query("DELETE FROM generation_attempts");
  await pool.query("UPDATE generation_limits SET lease_token=NULL,lease_until=NULL,blocked_until=NULL");
  expect((await request.post(llmURL+"/control",{data:{mode:"answered"}})).ok()).toBe(true);
});
test.afterAll(async()=>{await pool.end();});
async function account(context:APIRequestContext,prefix:string) {
  expect((await context.post("/api/auth/sign-up/username",{headers:{origin:baseURL},data:{
    username:`${prefix}.t${Date.now()}${Math.floor(Math.random()*1000)}`,password:"Local answer password 2026!"}})).status()).toBe(200);
}
async function upload(context:APIRequestContext) {
  const bytes=Buffer.from(facts);
  const reserve=await context.post("/api/v1/documents/uploads",{headers:{origin:baseURL},data:{filename:"oriole.txt",size_bytes:bytes.length,content_type:"text/plain"}});
  expect(reserve.status()).toBe(201);const value=await reserve.json();
  expect((await context.put(value.upload_url,{data:bytes,headers:{origin:baseURL,authorization:`Bearer ${value.upload_token}`,"content-type":"text/plain"}})).status()).toBe(204);
  expect((await context.post("/api/v1/documents",{headers:{origin:baseURL},data:{upload_id:value.document.id}})).status()).toBe(202);
  await expect.poll(async()=>(await(await context.get(`/api/v1/documents/${value.document.id}`)).json()).state,{timeout:120000}).toBe("ready");
  return value.document.id as string;
}
const body={question:facts,allow_external_processing:true};

test("réponse sourcée réelle dans le navigateur, consentement, source exacte et isolation",async({page})=>{
  test.setTimeout(180000);await account(page.request,"answeralice");const id=await upload(page.request);
  await page.goto("/search");await page.getByLabel("Votre question").fill(facts);
  const button=page.getByRole("button",{name:"Générer une réponse sourcée"});await expect(button).toBeDisabled();
  await page.getByRole("checkbox",{name:/J’accepte l’envoi/}).check();await button.click();
  await expect(page.locator(".answer-claims")).toContainText("Le lancement a lieu à Lyon.",{timeout:120000});
  await page.getByRole("link",{name:"[S1]"}).click();
  await page.getByText("Vérifier la source S1",{exact:true}).click();
  // The provider selects the server's exact paragraph, including both sentences.
  await expect(page.locator(".answer-source blockquote")).toHaveText(facts);
  await expect(page.locator(".answer-source pre")).toHaveText(facts);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect(await page.evaluate(()=>Object.values(localStorage))).toEqual([]);
  await page.screenshot({path:test.info().outputPath("answer-private.png"),fullPage:true});
  const bob=await apiRequest.newContext({baseURL});
  try { await account(bob,"answerbob");
    expect((await bob.post("/api/v1/answers",{headers:{origin:baseURL},data:{...body,document_ids:[id]}})).status()).toBe(404);
  } finally { await bob.dispose(); }
  expect((await page.request.post("/api/v1/answers",{headers:{origin:baseURL},data:{question:facts}})).status()).toBe(403);
  expect((await(await page.request.get(llmURL+"/control")).json()).calls).toBe(1);
});

test("citation inventée rejetée et quota fournisseur sans faux succès",async({page})=>{
  test.setTimeout(180000);await account(page.request,"answererror");await upload(page.request);
  await page.goto("/search");await page.getByLabel("Votre question").fill(facts);
  await page.getByRole("checkbox",{name:/J’accepte l’envoi/}).check();
  await page.request.post(llmURL+"/control",{data:{mode:"invalid"}});
  await page.getByRole("button",{name:"Générer une réponse sourcée"}).click();
  const alert=page.getByRole("region",{name:"Rechercher dans mes documents"}).getByRole("alert");
  await expect(alert).toContainText("référence ou un extrait invalide",{timeout:120000});
  await expect(page.locator(".answer-claims")).toHaveCount(0);
  await page.request.post(llmURL+"/control",{data:{mode:"quota"}});
  await page.getByRole("button",{name:"Générer une réponse sourcée"}).click();
  await expect(alert).toContainText("quota Groq est atteint",{timeout:120000});
  expect((await page.request.post("/api/v1/answers",{headers:{origin:baseURL},data:body})).status()).toBe(429);
  expect((await(await page.request.get(llmURL+"/control")).json()).calls).toBe(1);
  await expect(page.locator(".answer-claims")).toHaveCount(0);
});

test("abstention du fournisseur et corpus vide sans appel ni quota",async({page})=>{
  test.setTimeout(180000);await account(page.request,"answerabsent");await upload(page.request);
  await page.request.post(llmURL+"/control",{data:{mode:"absent"}});
  const answer=await page.request.post("/api/v1/answers",{headers:{origin:baseURL},data:body});
  expect(answer.status()).toBe(200);expect((await answer.json()).state).toBe("insufficient_context");
  await page.request.post("/api/auth/sign-out",{headers:{origin:baseURL},data:{}});
  expect((await page.request.post("/api/v1/answers",{data:body})).status()).toBe(401);
  await account(page.request,"answerempty");
  const empty=await page.request.post("/api/v1/answers",{headers:{origin:baseURL},data:{question:"Question"}});
  expect(empty.status()).toBe(200);const result=await empty.json();
  expect(result.state).toBe("insufficient_context");expect(result.provider_called).toBe(false);
  expect((await(await page.request.get(llmURL+"/control")).json()).calls).toBe(1);
});

for (const mutation of ["source", "session"] as const) test(`publication refusée après suppression de ${mutation} pendant Groq`,async({page})=>{
  test.setTimeout(180000);await account(page.request,`answerrace${mutation}`);const id=await upload(page.request);
  await page.request.post(llmURL+"/control",{data:{mode:"pause"}});
  const response=page.request.post("/api/v1/answers",{headers:{origin:baseURL},data:body,timeout:180000});
  await expect.poll(async()=>(await(await page.request.get(llmURL+"/control")).json()).calls,{timeout:120000}).toBe(1);
  if(mutation==="source") expect((await page.request.delete(`/api/v1/documents/${id}`,{headers:{origin:baseURL}})).status()).toBe(202);
  else expect((await page.request.post("/api/auth/sign-out",{headers:{origin:baseURL},data:{}})).status()).toBe(200);
  await page.request.post(llmURL+"/control",{data:{release:true}});
  const rejected=await response;expect(rejected.status()).toBe(mutation==="source"?409:401);
  expect(await rejected.text()).not.toContain("Lyon");
});
