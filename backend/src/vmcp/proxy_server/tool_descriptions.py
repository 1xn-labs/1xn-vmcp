"""
Tool descriptions for preset tools in the proxy server.
Keeping descriptions separate for better readability and maintenance.
"""

UPLOAD_PROMPT_DESCRIPTION = """Create a custom prompt in the active MCP configuration. 

IMPORTANT: USE THIS TOOL ONLY WHEN SPECIALLY REQUESTED BY THE USER.


INPUT FORMAT:
The tool accepts a single JSON object containing all prompt configuration.

VARIABLES EXPLANATION:
Variables are placeholders in prompt text that can be filled with different values each time the prompt is used.
- Variables are referenced in prompt text using the format: @param.variableName
- Each variable has a name, description, and required flag
- When the prompt is used, users will be prompted to provide values for these variables
- Variables make prompts flexible and reusable for different contexts

JSON EXAMPLE WITHOUT VARIABLES (Simple Static Prompt):
{
  "name": "meeting_summarizer",
  "description": "Summarize meeting notes",
  "text": "Please summarize the following meeting notes in bullet points, highlighting key decisions and action items."
}

JSON EXAMPLE WITH VARIABLES (Dynamic Prompt):
{
  "name": "code_reviewer",
  "description": "Review code with specific focus areas",
  "text": "Review this @param.language code focusing on @param.focus_area. Provide feedback on @param.code",
  "variables": [
    {
      "name": "language",
      "description": "Programming language (e.g., Python, JavaScript)",
      "required": true
    },
    {
      "name": "focus_area", 
      "description": "What to focus on (performance, security, readability)",
      "required": false
    },
    {
      "name": "code",
      "description": "The actual code to review", 
      "required": true
    }
  ]
}
"""

VMCP_CREATE_PROMPT_DESCRIPTION = """Create a custom prompt in the active vMCP configuration. 

IMPORTANT: Use this tool only when specifically requested by the user to create a new reusable prompt template.

WHAT THIS TOOL DOES:
- Creates a new custom prompt that becomes available in the current vMCP
- Allows creation of dynamic prompts with user-defined variables
- Stores the prompt permanently in the vMCP configuration for future use
- Enables prompt reuse across different conversations and sessions

INPUT FORMAT:
The tool accepts a single JSON object containing all prompt configuration.

VARIABLES EXPLANATION:
Variables are placeholders in prompt text that can be filled with different values each time the prompt is used.
- Variables are referenced in prompt text using the format: @param.variableName
- Each variable has a name, description, and required flag
- When the prompt is used, users will be prompted to provide values for these variables
- Variables make prompts flexible and reusable for different contexts

JSON EXAMPLE WITHOUT VARIABLES (Simple Static Prompt):
{
  "name": "meeting_summarizer",
  "description": "Summarize meeting notes",
  "text": "Please summarize the following meeting notes in bullet points, highlighting key decisions and action items."
}

JSON EXAMPLE WITH VARIABLES (Dynamic Prompt):
{
  "name": "code_reviewer",
  "description": "Review code with specific focus areas",
  "text": "Review this @param.language code focusing on @param.focus_area. Provide feedback on @param.code",
  "variables": [
    {
      "name": "language",
      "description": "Programming language (e.g., Python, JavaScript)",
      "required": true
    },
    {
      "name": "focus_area", 
      "description": "What to focus on (performance, security, readability)",
      "required": false
    },
    {
      "name": "code",
      "description": "The actual code to review", 
      "required": true
    }
  ]
}

ANOTHER EXAMPLE WITH ARGUMENTS (Task Planning Prompt):
{
  "name": "task_planner",
  "description": "Create a structured plan for completing tasks",
  "text": "Create a detailed plan for: @param.task_description. Break it into @param.num_steps steps. Consider @param.timeline and @param.resources available.",
  "variables": [
    {
      "name": "task_description",
      "description": "The main task or project to plan for",
      "required": true
    },
    {
      "name": "num_steps",
      "description": "Number of steps to break the task into",
      "required": false
    },
    {
      "name": "timeline",
      "description": "Available time frame for completion",
      "required": false
    },
    {
      "name": "resources",
      "description": "Available resources (people, tools, budget)",
      "required": false
    }
  ]
}

WHEN TO USE VARIABLES:
- Use variables when you need the same prompt structure with different inputs
- Use for prompts that will be reused with different data/contexts  
- Avoid variables for simple, static prompts that don't need customization

BEST PRACTICES:
- Keep variable names short and descriptive
- Use clear descriptions for each variable
- Mark variables as required only when absolutely necessary
- Use variables only when necessary. Do not unnecessarily use variables. Simple static prompts should not have variables.
- Test your prompt with sample variable values before creating it"""








CREATE_PROMPT_HELPER_TEXT = """Create a custom prompt in the mcp
BASED on the title {title}
and the description {description}

IMPORTANT: Use this tool only when specifically requested by the user to create a new reusable prompt template.

WHAT THIS TOOL DOES:
- Creates a new custom prompt that becomes available in the current vMCP
- Allows creation of dynamic prompts with user-defined variables
- Stores the prompt permanently in the vMCP configuration for future use
- Enables prompt reuse across different conversations and sessions

INPUT FORMAT:
The tool accepts a single JSON object containing all prompt configuration.

VARIABLES EXPLANATION:
Variables are placeholders in prompt text that can be filled with different values each time the prompt is used.
- Variables are referenced in prompt text using the format: @param.variableName
- Each variable has a name, description, and required flag
- When the prompt is used, users will be prompted to provide values for these variables
- Variables make prompts flexible and reusable for different contexts

JSON EXAMPLE WITHOUT VARIABLES (Simple Static Prompt):
{
  "name": "meeting_summarizer",
  "description": "Summarize meeting notes",
  "text": "Please summarize the following meeting notes in bullet points, highlighting key decisions and action items."
}

JSON EXAMPLE WITH VARIABLES (Dynamic Prompt):
{
  "name": "code_reviewer",
  "description": "Review code with specific focus areas",
  "text": "Review this @param.language code focusing on @param.focus_area. Provide feedback on @param.code",
  "variables": [
    {
      "name": "language",
      "description": "Programming language (e.g., Python, JavaScript)",
      "required": true
    },
    {
      "name": "focus_area", 
      "description": "What to focus on (performance, security, readability)",
      "required": false
    },
    {
      "name": "code",
      "description": "The actual code to review", 
      "required": true
    }
  ]
}

WHEN TO USE VARIABLES:
- Use variables when you need the same prompt structure with different inputs
- Use for prompts that will be reused with different data/contexts  
- Avoid variables for simple, static prompts that don't need customization

BEST PRACTICES:
- Keep variable names short and descriptive
- Use clear descriptions for each variable
- Mark variables as required only when absolutely necessary
- Use variables only when necessary. Do not unnecessarily use variables. Simple static prompts should not have variables"""
