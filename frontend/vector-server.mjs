// Embedded PostgreSQL with the actual pgvector extension. No original-store writes.
import { PGlite } from '@electric-sql/pglite'
import { vector } from '@electric-sql/pglite-pgvector'
import http from 'node:http'
import { readFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dbDir = path.join(root, 'runtime', 'pgvector')
await mkdir(dbDir, {recursive: true})
const db = await PGlite.create(dbDir, {extensions: {vector}})
await db.exec('CREATE EXTENSION IF NOT EXISTS vector; CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY, file_path TEXT, content TEXT, embedding vector(1024));')
const seedFile = path.join(root, 'runtime', 'pgvector-seed.json')
const existing = await db.query('SELECT count(*)::int AS count FROM chunks')
if (!existing.rows[0].count) {
 const rows = JSON.parse(await readFile(seedFile,'utf8'))
 await db.transaction(async(tx)=>{
  for (const row of rows) await tx.query('INSERT INTO chunks VALUES ($1,$2,$3,$4) ON CONFLICT(id) DO NOTHING', [row.id,row.file_path,row.content,JSON.stringify(row.vector)])
 })
 console.log(`Imported ${rows.length} copied LightRAG chunks into pgvector`)
}
const server = http.createServer(async(req,res)=>{
 res.setHeader('Content-Type','application/json; charset=utf-8')
 try {
  if(req.method==='GET'&&req.url==='/health'){
   const result = await db.query("SELECT (SELECT count(*)::int FROM chunks) AS chunks,(SELECT extversion FROM pg_extension WHERE extname='vector') AS version")
   res.end(JSON.stringify({status:'ok',engine:'PGlite PostgreSQL + pgvector',...result.rows[0]}));return
  }
  if(req.method==='POST'&&req.url==='/search'){
   let text='';for await(const chunk of req){text+=chunk;if(text.length>100000)throw Error('Body too large')}
   const body=JSON.parse(text), embedding=body.embedding
   if(!Array.isArray(embedding)||embedding.length!==1024||!embedding.every(Number.isFinite))throw Error('Invalid embedding')
   const limit=Math.min(8,Math.max(1,Number(body.limit)||6))
   const result=await db.query('SELECT id AS chunk_id,file_path,content,1-(embedding <=> $1::vector) AS similarity FROM chunks ORDER BY embedding <=> $1::vector LIMIT $2',[JSON.stringify(embedding),limit])
   res.end(JSON.stringify({chunks:result.rows}));return
  }
  res.statusCode=404;res.end(JSON.stringify({error:'Not found'}))
 }catch{res.statusCode=400;res.end(JSON.stringify({error:'Vector request failed'}))}
})
server.listen(8510,'127.0.0.1',()=>console.log('PGvector service http://127.0.0.1:8510'))
for (const signal of ['SIGINT','SIGTERM']) process.on(signal,async()=>{server.close();await db.close();process.exit(0)})
