"""Serverless gateway entry point. Use durable external infrastructure in the cloud."""
from mangum import Mangum

from crabgraph.api import app

# A deployable API adapter, not a claim that local background jobs are cloud durable.
handler = Mangum(app, lifespan="off")
