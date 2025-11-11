"""
OpenTelemetry tracing setup for vMCP.

Provides distributed tracing similar to Langflow's implementation.
Traces can be exported to Jaeger, Zipkin, or any OTLP-compatible backend.
"""

import functools
import logging
from typing import Any, Callable, Optional

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.asyncio import AsyncioInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from vmcp.config import settings

logger = logging.getLogger(__name__)

# Global tracer
_tracer: Optional[trace.Tracer] = None


def setup_telemetry() -> None:
    """
    Setup OpenTelemetry tracing.

    This configures the tracer provider and sets up automatic instrumentation
    for FastAPI, SQLAlchemy, HTTPX, and asyncio.
    """
    global _tracer

    if not settings.enable_tracing:
        logger.info("Tracing is disabled")
        return

    try:
        # Create resource with service information
        resource = Resource.create({
            "service.name": settings.service_name,
            "service.version": settings.app_version,
        })

        # Setup tracer provider
        provider = TracerProvider(resource=resource)

        # Setup OTLP exporter if endpoint is configured
        if settings.otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)
            span_processor = BatchSpanProcessor(otlp_exporter)
            provider.add_span_processor(span_processor)
            logger.info(f"OTLP tracing enabled, exporting to: {settings.otlp_endpoint}")
        else:
            logger.warning("Tracing enabled but no OTLP endpoint configured")

        # Set as global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer instance
        _tracer = trace.get_tracer(__name__)

        # Setup automatic instrumentation
        AsyncioInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()

        logger.info("OpenTelemetry tracing initialized")

    except Exception as e:
        logger.error(f"Failed to setup tracing: {e}", exc_info=True)


def instrument_fastapi(app: Any) -> None:
    """
    Instrument FastAPI application for tracing.

    Args:
        app: FastAPI application instance
    """
    if settings.enable_tracing:
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")


def instrument_sqlalchemy(engine: Any) -> None:
    """
    Instrument SQLAlchemy engine for tracing.

    Args:
        engine: SQLAlchemy engine instance
    """
    if settings.enable_tracing:
        try:
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("SQLAlchemy instrumentation enabled")
        except Exception as e:
            logger.error(f"Failed to instrument SQLAlchemy: {e}")


def get_tracer() -> trace.Tracer:
    """
    Get the global tracer instance.

    Returns:
        Tracer instance
    """
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(__name__)
    return _tracer


def trace_method(name: str = None, **trace_kwargs):
    """
    Decorator to trace a function or method.

    Args:
        name: Span name (defaults to function name)
        **trace_kwargs: Additional attributes to add to the span

    Usage:
        @trace_method("operation_name")
        def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        if not settings.enable_tracing:
            return func

        span_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                # Add custom attributes
                for key, value in trace_kwargs.items():
                    span.set_attribute(key, value)

                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


def trace_async(name: str = None, **trace_kwargs):
    """
    Decorator to trace an async function or method.

    Args:
        name: Span name (defaults to function name)
        **trace_kwargs: Additional attributes to add to the span

    Usage:
        @trace_async("async_operation")
        async def my_async_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        if not settings.enable_tracing:
            return func

        span_name = name or f"{func.__module__}.{func.__name__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                # Add custom attributes
                for key, value in trace_kwargs.items():
                    span.set_attribute(key, value)

                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("success", True)
                    return result
                except Exception as e:
                    span.set_attribute("success", False)
                    span.set_attribute("error", str(e))
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


def add_event(event_name: str, **attributes):
    """
    Add an event to the current span.

    For OSS version: This is a no-op stub since tracing is disabled by default.

    Args:
        event_name: Name of the event
        **attributes: Additional attributes for the event
    """
    if not settings.enable_tracing:
        return

    try:
        span = trace.get_current_span()
        if span and span.is_recording():
            span.add_event(event_name, attributes=attributes)
    except Exception as e:
        logger.debug(f"Failed to add event to span: {e}")


def log_to_span(message: str, **attributes):
    """
    Log a message to the current span with optional attributes.

    For OSS version: This is a no-op stub since tracing is disabled by default.

    Args:
        message: Message to log
        **attributes: Additional attributes to add to the span
    """
    if not settings.enable_tracing:
        return

    try:
        span = trace.get_current_span()
        if span and span.is_recording():
            span.add_event(message, attributes=attributes)
            for key, value in attributes.items():
                span.set_attribute(key, value)
    except Exception as e:
        logger.debug(f"Failed to log to span: {e}")


def add_tracing_middleware(app, service_name: str, excluded_paths: set = None, excluded_prefixes: set = None):
    """
    Add OpenTelemetry tracing middleware to FastAPI app.

    For OSS version: This is a no-op stub since tracing is disabled by default.
    If tracing is enabled via settings, FastAPI instrumentation happens in setup_telemetry().
    """
    if not settings.enable_tracing:
        logger.debug("Tracing middleware not added (tracing disabled)")
        return

    # If tracing is enabled, the FastAPIInstrumentor in setup_telemetry() already handles it
    logger.info(f"Tracing middleware configured for {service_name}")
