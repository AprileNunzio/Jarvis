import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import FastAPI

def setup_telemetry(app: FastAPI):
    # Abilita la telemetria solo se OTLP_ENDPOINT è configurato
    otlp_endpoint = os.getenv("OTLP_ENDPOINT")
    if not otlp_endpoint:
        logging.getLogger("jarvis.telemetry").info("OTLP_ENDPOINT non configurato. Telemetria disabilitata.")
        return

    provider = TracerProvider()
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    logging.getLogger("jarvis.telemetry").info(f"Telemetria OpenTelemetry configurata su {otlp_endpoint}")

def get_tracer(name: str):
    return trace.get_tracer(name)
