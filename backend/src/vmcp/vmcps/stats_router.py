import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException

# Import dependencies
from vmcp.storage.database import SessionLocal
from vmcp.storage.dummy_user import UserContext, get_user_context
from vmcp.storage.models import VMCP, VMCPStats

# Import type-safe models
from vmcp.vmcps.models import (
    LogEntry,
    PaginationInfo,
    StatsFilterRequest,
    StatsResponse,
    StatsSummary,
)

logger = logging.getLogger(__name__)


router = APIRouter(tags=["Stats"])

@router.post("/stats", response_model=StatsResponse)
async def get_stats(request: StatsFilterRequest, user_context: UserContext = Depends(get_user_context)):
    """Get paginated stats with filtering capabilities"""
    logger.info(f"📊 Stats endpoint called for user: {user_context.user_id}")
    logger.info(f"   🔍 Filters: agent_name={request.agent_name}, vmcp_name={request.vmcp_name}, method={request.method}")
    logger.info(f"   📄 Pagination: page={request.page}, limit={request.limit}")

    try:
        # OSS: Query VMCPStats from database
        session = SessionLocal()
        try:
            stats_records = session.query(VMCPStats).join(VMCP).filter(
                VMCP.user_id == user_context.user_id
            ).order_by(VMCPStats.created_at.desc()).all()

            # Convert to log format with rich data from operation_metadata
            all_logs = []
            for stat in stats_records:
                metadata = stat.operation_metadata or {}
                all_logs.append({
                    "timestamp": stat.created_at.isoformat() if stat.created_at else None,
                    "method": stat.operation_type,
                    "agent_name": metadata.get("agent_name", "unknown"),
                    "agent_id": metadata.get("agent_id", "unknown"),
                    "user_id": metadata.get("user_id", user_context.user_id),
                    "client_id": metadata.get("client_id", "unknown"),
                    "operation_id": metadata.get("operation_id", "N/A"),
                    "mcp_server": stat.mcp_server_id,
                    "mcp_method": stat.operation_type,
                    "original_name": stat.operation_name,
                    "arguments": metadata.get("arguments", "No arguments"),
                    "result": metadata.get("result", "No result"),
                    "vmcp_id": stat.vmcp_id,
                    "vmcp_name": metadata.get("vmcp_name", stat.vmcp.vmcp_id if stat.vmcp else "unknown"),
                    "total_tools": metadata.get("total_tools", 0),
                    "total_resources": metadata.get("total_resources", 0),
                    "total_resource_templates": metadata.get("total_resource_templates", 0),
                    "total_prompts": metadata.get("total_prompts", 0),
                    "success": stat.success,
                    "error_message": stat.error_message,
                    "duration_ms": stat.duration_ms
                })
        finally:
            session.close()

        if not all_logs:
            return StatsResponse(
                logs=[],
                pagination=PaginationInfo(
                    page=request.page,
                    limit=request.limit,
                    total=0,
                    pages=0
                ),
                stats=StatsSummary(
                    total_logs=0,
                    total_agents=0,
                    total_vmcps=0,
                    total_tool_calls=0,
                    total_resource_calls=0,
                    total_prompt_calls=0,
                    unique_methods=[],
                    agent_breakdown={},
                    vmcp_breakdown={},
                    method_breakdown={}
                ),
                filter_options={
                    "agent_names": [],
                    "vmcp_names": [],
                    "methods": []
                }
            )

        # Apply filters
        filtered_logs = all_logs.copy()

        if request.agent_name:
            agent_names = [name.strip() for name in request.agent_name.split(',') if name.strip()]
            filtered_logs = [log for log in filtered_logs if any(
                agent_name.lower() in log.get("agent_name", "").lower() for agent_name in agent_names
            )]

        if request.vmcp_name:
            vmcp_names = [name.strip() for name in request.vmcp_name.split(',') if name.strip()]
            filtered_logs = [log for log in filtered_logs if any(
                vmcp_name.lower() in log.get("vmcp_name", "").lower() for vmcp_name in vmcp_names
            )]

        if request.method:
            methods = [method.strip() for method in request.method.split(',') if method.strip()]
            filtered_logs = [log for log in filtered_logs if any(
                method.lower() in log.get("method", "").lower() for method in methods
            )]

        if request.search:
            search_term = request.search.lower()
            filtered_logs = [log for log in filtered_logs if
                search_term in log.get("agent_name", "").lower() or
                search_term in log.get("vmcp_name", "").lower() or
                search_term in log.get("method", "").lower() or
                search_term in log.get("mcp_server", "").lower() or
                search_term in log.get("operation_id", "").lower() or
                search_term in str(log.get("arguments", "")).lower() or
                search_term in str(log.get("result", "")).lower()
            ]

        # Calculate stats from filtered logs
        total_logs = len(filtered_logs)

        # Calculate filter options from ALL logs (not filtered) so users can see all available options
        all_unique_agents = {str(log.get("agent_name", "unknown")) for log in all_logs}
        all_unique_vmcps = {str(log.get("vmcp_name", "unknown")) for log in all_logs}
        all_unique_methods = {str(log.get("method", "unknown")) for log in all_logs}

        # Calculate stats for filtered results
        unique_agents = {str(log.get("agent_name", "unknown")) for log in filtered_logs}
        unique_vmcps = {str(log.get("vmcp_name", "unknown")) for log in filtered_logs}
        unique_methods = {str(log.get("method", "unknown")) for log in filtered_logs}

        # Count different types of calls
        tool_calls = len([log for log in filtered_logs if log.get("method") in ["tool_list", "tool_call"]])
        resource_calls = len([log for log in filtered_logs if log.get("method") in ["resource_list", "resource_get"]])
        prompt_calls = len([log for log in filtered_logs if log.get("method") in ["prompt_list", "prompt_get"]])

        # Calculate breakdowns
        agent_breakdown: dict[str, int] = {}
        for log in filtered_logs:
            agent_name = log.get("agent_name", "unknown")
            agent_breakdown[agent_name] = agent_breakdown.get(agent_name, 0) + 1

        vmcp_breakdown: dict[str, int] = {}
        for log in filtered_logs:
            vmcp_name = log.get("vmcp_name", "unknown")
            if vmcp_name:
                vmcp_breakdown[vmcp_name] = vmcp_breakdown.get(vmcp_name, 0) + 1

        method_breakdown: dict[str, int] = {}
        for log in filtered_logs:
            method = log.get("method", "unknown")
            method_breakdown[method] = method_breakdown.get(method, 0) + 1

        # Pagination
        total_pages = (total_logs + request.limit - 1) // request.limit
        start_index = (request.page - 1) * request.limit
        end_index = start_index + request.limit
        paginated_logs = filtered_logs[start_index:end_index]

        # Convert to LogEntry objects
        log_entries = []
        for log in paginated_logs:
            try:
                log_entry = LogEntry(
                    timestamp=log.get("timestamp", ""),
                    method=log.get("method", ""),
                    agent_name=log.get("agent_name", ""),
                    agent_id=log.get("agent_id", ""),
                    user_id=log.get("user_id", 0),
                    client_id=log.get("client_id", ""),
                    operation_id=log.get("operation_id", ""),
                    mcp_server=log.get("mcp_server"),
                    mcp_method=log.get("mcp_method"),
                    original_name=log.get("original_name"),
                    arguments=log.get("arguments"),
                    result=log.get("result"),
                    vmcp_id=log.get("vmcp_id"),
                    vmcp_name=log.get("vmcp_name"),
                    total_tools=log.get("total_tools"),
                    total_resources=log.get("total_resources"),
                    total_resource_templates=log.get("total_resource_templates"),
                    total_prompts=log.get("total_prompts")
                )
                log_entries.append(log_entry)
            except Exception as e:
                logger.warning(f"Failed to parse log entry: {e}")
                continue

        return StatsResponse(
            logs=log_entries,
            pagination=PaginationInfo(
                page=request.page,
                limit=request.limit,
                total=total_logs,
                pages=total_pages
            ),
            stats=StatsSummary(
                total_logs=total_logs,
                total_agents=len(unique_agents),
                total_vmcps=len(unique_vmcps),
                total_tool_calls=tool_calls,
                total_resource_calls=resource_calls,
                total_prompt_calls=prompt_calls,
                unique_methods=sorted(unique_methods),
                agent_breakdown=agent_breakdown,
                vmcp_breakdown=vmcp_breakdown,
                method_breakdown=method_breakdown
            ),
            filter_options={
                "agent_names": sorted(all_unique_agents),
                "vmcp_names": sorted(all_unique_vmcps),
                "methods": sorted(all_unique_methods)
            }
        )

    except Exception as e:
        logger.error(f"   ❌ Error fetching stats: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}") from e

@router.get("/stats/summary", response_model=StatsSummary)
async def get_stats_summary(user_context: UserContext = Depends(get_user_context)):
    """Get overall stats summary without pagination"""
    logger.info(f"📊 Stats summary endpoint called for user: {user_context.user_id}")

    try:
        # OSS: Query VMCPStats from database
        session = SessionLocal()
        try:
            stats_records = session.query(VMCPStats).join(VMCP).filter(
                VMCP.user_id == user_context.user_id
            ).order_by(VMCPStats.created_at.desc()).all()

            # Convert to log format with rich data from operation_metadata
            all_logs = []
            for stat in stats_records:
                metadata = stat.operation_metadata or {}
                all_logs.append({
                    "timestamp": stat.created_at.isoformat() if stat.created_at else None,
                    "method": stat.operation_type,
                    "agent_name": metadata.get("agent_name", "unknown"),
                    "agent_id": metadata.get("agent_id", "unknown"),
                    "user_id": metadata.get("user_id", user_context.user_id),
                    "client_id": metadata.get("client_id", "unknown"),
                    "operation_id": metadata.get("operation_id", "N/A"),
                    "mcp_server": stat.mcp_server_id,
                    "mcp_method": stat.operation_type,
                    "original_name": stat.operation_name,
                    "arguments": metadata.get("arguments", "No arguments"),
                    "result": metadata.get("result", "No result"),
                    "vmcp_id": stat.vmcp_id,
                    "vmcp_name": metadata.get("vmcp_name", stat.vmcp.vmcp_id if stat.vmcp else "unknown"),
                    "total_tools": metadata.get("total_tools", 0),
                    "total_resources": metadata.get("total_resources", 0),
                    "total_resource_templates": metadata.get("total_resource_templates", 0),
                    "total_prompts": metadata.get("total_prompts", 0),
                    "success": stat.success,
                    "error_message": stat.error_message,
                    "duration_ms": stat.duration_ms
                })
        finally:
            session.close()

        if not all_logs:
            return StatsSummary(
                total_logs=0,
                total_agents=0,
                total_vmcps=0,
                total_tool_calls=0,
                total_resource_calls=0,
                total_prompt_calls=0,
                unique_methods=[],
                agent_breakdown={},
                vmcp_breakdown={},
                method_breakdown={}
            )

        # Calculate stats
        total_logs = len(all_logs)
        unique_agents = {str(log.get("agent_name", "unknown")) for log in all_logs}
        unique_vmcps = {str(log.get("vmcp_name", "unknown")) for log in all_logs if log.get("vmcp_name")}
        unique_methods = {str(log.get("method", "unknown")) for log in all_logs}

        # Count different types of calls
        tool_calls = len([log for log in all_logs if log.get("method") in ["tool_list", "tool_call"]])
        resource_calls = len([log for log in all_logs if log.get("method") in ["resource_list", "resource_get"]])
        prompt_calls = len([log for log in all_logs if log.get("method") in ["prompt_list", "prompt_get"]])

        # Calculate breakdowns
        agent_breakdown: dict[str, int] = {}
        for log in all_logs:
            agent_name = log.get("agent_name", "unknown")
            agent_breakdown[agent_name] = agent_breakdown.get(agent_name, 0) + 1

        vmcp_breakdown: dict[str, int] = {}
        for log in all_logs:
            vmcp_name = log.get("vmcp_name", "unknown")
            if vmcp_name:
                vmcp_breakdown[vmcp_name] = vmcp_breakdown.get(vmcp_name, 0) + 1

        method_breakdown: dict[str, int] = {}
        for log in all_logs:
            method = log.get("method", "unknown")
            method_breakdown[method] = method_breakdown.get(method, 0) + 1

        return StatsSummary(
            total_logs=total_logs,
            total_agents=len(unique_agents),
            total_vmcps=len(unique_vmcps),
            total_tool_calls=tool_calls,
            total_resource_calls=resource_calls,
            total_prompt_calls=prompt_calls,
            unique_methods=sorted(unique_methods),
            agent_breakdown=agent_breakdown,
            vmcp_breakdown=vmcp_breakdown,
            method_breakdown=method_breakdown
        )

    except Exception as e:
        logger.error(f"   ❌ Error fetching stats summary: {e}")
        logger.error(f"   ❌ Exception type: {type(e).__name__}")
        logger.error(f"   ❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats summary: {str(e)}") from e

