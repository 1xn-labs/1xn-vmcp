import React from 'react';
// @ts-ignore - Babel standalone doesn't have proper types
import * as Babel from '@babel/standalone';

/**
 * TSX Code Execution System using Babel Standalone
 * 
 * This system allows running TSX code strings as React components using
 * proper Babel transpilation for JSX and TypeScript support.
 * 
 * SECURITY NOTE: This should only be used with trusted code in development
 * environments. For production, you'd want proper sandboxing.
 */

// Configure Babel presets
Babel.registerPreset('tsx', {
  presets: [
    [Babel.availablePresets['typescript'], { 
      isTSX: true, 
      allExtensions: true,
      allowNamespaces: true
    }],
    [Babel.availablePresets['react'], { 
      runtime: 'classic',
      pragma: 'React.createElement',
      pragmaFrag: 'React.Fragment'
    }]
  ]
});

// Available imports for TSX code
function getAvailableImports(additionalContext: Record<string, any> = {}) {
  return {
    React,
    useState: React.useState,
    useEffect: React.useEffect,
    useMemo: React.useMemo,
    useCallback: React.useCallback,
    useRef: React.useRef,
    useContext: React.useContext,
    useReducer: React.useReducer,
    useLayoutEffect: React.useLayoutEffect,
    useImperativeHandle: React.useImperativeHandle,
    // Add console access for debugging
    console: window.console,
    // Add additional context (like useNApp hook)
    ...additionalContext
  };
}

// Transform TSX code using Babel
function transformTSX(code: string): string {
  try {
    const result = Babel.transform(code, {
      presets: ['tsx'],
      filename: 'component.tsx'
    });
    
    return result.code || '';
  } catch (error) {
    // console.error('Babel transformation error:', error);
    throw new Error(`TSX transformation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

// Extract component name from TSX code
function extractComponentName(code: string): string {
  const match = code.match(/export\s+default\s+function\s+(\w+)/);
  return match ? match[1] : 'CustomComponent';
}

/**
 * Execute TSX code and return a React component
 */
export function executeTSXCode(
  tsxCode: string, 
  additionalContext: Record<string, any> = {}
): React.ComponentType | null {
  try {
    // Basic security check - reject obviously dangerous code
    const dangerousPatterns = [
      /eval\s*\(/,
      /Function\s*\(/,
      /window\./,
      /document\./,
      /global\./,
      /process\./,
      /__dirname/,
      /__filename/,
      /require\s*\(/,
      /fetch\s*\(/,
      /XMLHttpRequest/,
      /localStorage/,
      /sessionStorage/
      // Note: console is now allowed for debugging
    ];
    
    for (const pattern of dangerousPatterns) {
      if (pattern.test(tsxCode)) {
        throw new Error(`Code contains potentially unsafe pattern: ${pattern.toString()}`);
      }
    }

    // Extract component name before transformation
    const componentName = extractComponentName(tsxCode);
    
    // Remove imports and exports since we'll inject them
    let cleanCode = tsxCode
      .replace(/import\s+.*?from\s+.*?;/g, '')
      .replace(/export\s+default\s+/g, '');
    
    // Transform TSX to JavaScript using Babel
    const transformedCode = transformTSX(cleanCode);
    console.log('🔄 Transformed TSX code:', transformedCode);
    
    // // Debug: Log each line of transformed code with line numbers
    // const transformedLines = transformedCode.split('\n');
    // console.log('🔍 Transformed code with line numbers:');
    // transformedLines.forEach((line, index) => {
    //   console.log(`${index + 1}: ${line}`);
    // });
    
    // Create execution context with available imports
    const context = getAvailableImports(additionalContext);
    const contextKeys = Object.keys(context);
    const contextValues = Object.values(context);
    
    // Create the function that returns the component
    const functionBody = `
      "use strict";
      try {
        // Execute the transformed code
        ${transformedCode}
        
        // Return the component function
        if (typeof ${componentName} === 'function') {
          return ${componentName};
        } else {
          throw new Error('Component "${componentName}" is not a function. Available: ' + Object.keys(this).join(', '));
        }
      } catch (error) {
        console.error('Component execution error:', error);
        console.error('Transformed code:', transformedCode);
        return function ErrorComponent() {
          return React.createElement('div', {
            style: { 
              padding: '20px', 
              border: '1px solid red', 
              borderRadius: '4px',
              backgroundColor: '#fee',
              color: 'red',
              fontFamily: 'monospace'
            }
          }, 
            React.createElement('h3', null, '❌ Component Execution Error'),
            React.createElement('p', null, error.message),
            React.createElement('details', null,
              React.createElement('summary', null, 'Stack Trace'),
              React.createElement('pre', { style: { fontSize: '10px', overflow: 'auto' } }, error.stack || 'No stack trace')
            ),
            React.createElement('details', null,
              React.createElement('summary', null, 'Transformed Code'),
              React.createElement('pre', { style: { fontSize: '8px', overflow: 'auto', maxHeight: '200px' } }, transformedCode)
            )
          );
        };
      }
      `;

    console.log('🏗️ About to create Function with:');
    console.log('Context keys:', contextKeys);
    // console.log('Function body:');
    // const functionBodyLines = functionBody.split('\n');
    // functionBodyLines.forEach((line, index) => {
    //   console.log(`FB${index + 1}: ${line}`);
    // });

    let componentFunction;
    try {
      componentFunction = new Function(...contextKeys, functionBody);
      console.log('✅ Function creation successful');
    } catch (funcError) {
      console.error('❌ Function creation failed:', funcError);
      console.error('Function body that caused the error:', functionBody);
      throw new Error(`❌ TSX execution error: ${funcError instanceof Error ? funcError.message : 'Unknown error'}`);
    }

    // Execute and get the component
    const Component = componentFunction(...contextValues);
    
    if (typeof Component !== 'function') {
      throw new Error('Code did not return a valid React component');
    }

    console.log('✅ TSX component executed successfully');
    return Component;
    
  } catch (error) {
    console.error('❌ TSX execution error:', error);
    
    // Return an error component
    return function TSXError() {
      return React.createElement('div', {
        style: { 
          padding: '20px', 
          border: '1px solid red', 
          borderRadius: '4px',
          backgroundColor: '#fee',
          color: 'red',
          fontFamily: 'monospace'
        }
      }, 
        React.createElement('h3', null, '❌ TSX Execution Error'),
        React.createElement('p', null, error instanceof Error ? error.message : 'Unknown error'),
        React.createElement('p', { style: { fontSize: '12px', marginTop: '10px' } }, 
          'Check the browser console for more details.'
        )
      );
    };
  }
}

/**
 * Alternative approach using a more sophisticated JSX transformer
 * This would be used in production with proper babel transformation
 */
export function executeTSXCodeAdvanced(tsxCode: string): Promise<React.ComponentType | null> {
  return new Promise((resolve) => {
    try {
      // In a real implementation, you would:
      // 1. Use @babel/standalone to transform JSX
      // 2. Use proper sandboxing (iframe, web workers, etc.)
      // 3. Implement proper import resolution
      // 4. Add comprehensive security checks
      
      // For now, fall back to the basic method
      const Component = executeTSXCode(tsxCode);
      resolve(Component);
    } catch (error) {
      console.error('Advanced TSX execution failed:', error);
      resolve(null);
    }
  });
}

/**
 * Validate TSX code without executing it
 */
export function validateTSXCode(code: string): { isValid: boolean; errors: string[] } {
  const errors: string[] = [];
  
  // Basic syntax checks
  if (!code.includes('export default function')) {
    errors.push('Code must export a default function component');
  }
  
  // Check for balanced brackets
  const openBraces = (code.match(/\{/g) || []).length;
  const closeBraces = (code.match(/\}/g) || []).length;
  if (openBraces !== closeBraces) {
    errors.push('Unbalanced braces in code');
  }
  
  // Check for basic JSX structure
  if (!code.includes('return')) {
    errors.push('Component must return JSX');
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
}