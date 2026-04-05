# Agent Memory Server OpenCode Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an OpenCode plugin that integrates agent-memory-server's persistent memory capabilities (working memory + long-term memory with semantic search) into OpenCode, providing automatic context injection, session compaction support, and a memory tool for AI agents.

**Architecture:** The plugin uses a TypeScript-based OpenCode plugin architecture with:
- REST API client connecting to agent-memory-server
- Event hooks for session lifecycle (created, idle, compacted, deleted)
- Chat message hook for automatic context injection
- Experimental compaction hook for pre-compaction context injection
- Custom tool definition for explicit memory operations
- JSONC configuration with environment variable support

**Tech Stack:** TypeScript, OpenCode Plugin SDK, fetch HTTP client, JSONC parsing

---

## 1. Feature Integration Matrix

| Feature | Source | Implementation |
|---------|--------|----------------|
| Context Injection (chat.message) | Supermemory | ✅ Implement |
| Profile/User injection | Supermemory | ✅ Implement |
| Project memory injection | Supermemory + opencode-mem | ✅ Implement |
| Compaction hook (pre) | Supermemory | ✅ Implement |
| Compaction hook (post/recovery) | opencode-mem | ✅ Implement |
| Auto-capture (session.idle) | opencode-mem | ✅ Implement |
| Session mapping | OpenViking | ⚠️ Optional |
| Message buffering | OpenViking | ❌ Skip (complexity) |
| Web UI | opencode-mem | ❌ Skip (future) |
| Tool: search_memory | agent-memory-client | ✅ Implement |
| Tool: add_memory | agent-memory-client | ✅ Implement |
| Tool: list_memory | agent-memory-client | ✅ Implement |
| Tool: get_memory | agent-memory-client | ✅ Implement |
| Tool: forget_memory | agent-memory-client | ✅ Implement |

---

## 2. File Structure

```
.opencode/plugins/agent-memory/
├── index.ts              # Main plugin entry point
├── config.ts             # Configuration loading and defaults
├── services/
│   ├── client.ts         # Agent Memory Server API client
│   ├── session.ts        # Session state management
│   ├── context.ts        # Context formatting for prompt injection
│   └── tags.ts           # Namespace/label generation
├── hooks/
│   ├── chat-message.ts   # chat.message hook implementation
│   ├── session.ts        # Session event handlers
│   └── compaction.ts      # Compaction hook implementation
├── tools/
│   └── memory.ts          # Memory tool definitions
├── types.ts              # TypeScript type definitions
├── utils/
│   ├── jsonc.ts          # JSONC parser
│   └── secret-resolver.ts # Environment/file secret resolution
├── package.json          # Dependencies
└── README.md             # Installation instructions
```

---

## 3. Configuration Schema

### 3.1 Configuration File: `~/.config/opencode/agent-memory.jsonc`

```jsonc
{
  // ========== Agent Memory Server Connection ==========
  "serverUrl": "http://localhost:8000",
  
  // API Key (optional, supports env:// and file://)
  // "apiKey": "env://AMS_API_KEY",
  
  // ========== Namespaces ==========
  // Use namespace prefix for organizing memories
  "namespacePrefix": "opencode",
  
  // ========== Context Injection ==========
  "chatMessage": {
    // Enable context injection on chat messages
    "enabled": true,
    
    // When to inject: "first" (first message only) | "always" (every message)
    "injectOn": "first",
    
    // Maximum memories to inject
    "maxMemories": 5,
    
    // Similarity threshold for memory search (0-1)
    "similarityThreshold": 0.6,
    
    // Search mode: "semantic" | "keyword" | "hybrid"
    "searchMode": "semantic",
    
    // Exclude memories from current session
    "excludeCurrentSession": true,
    
    // Maximum age of memories to include (days, null = no limit)
    "maxAgeDays": 30
  },
  
  // ========== Compaction Hooks ==========
  "compaction": {
    // Enable compaction hooks
    "enabled": true,
    
    // Pre-compaction: inject context before summarization
    "injectBeforeCompaction": true,
    
    // Post-compaction: inject memories after session compacted
    "injectAfterCompaction": true,
    
    // Maximum memories to inject during compaction
    "memoryLimit": 10
  },
  
  // ========== Auto-Capture ==========
  "autoCapture": {
    // Enable automatic memory capture on session.idle
    "enabled": true,
    
    // Delay after idle before triggering capture (ms)
    "idleDelayMs": 10000,
    
    // Strategy: "discrete" | "summary"
    "strategy": "summary",
    
    // Only capture technical conversations
    "technicalOnly": true
  },
  
  // ========== Tool Settings ==========
  "tools": {
    // Enable memory tools
    "enabled": true,
    
    // Tool name prefix
    "namePrefix": "memory"
  },
  
  // ========== Toast Notifications ==========
  "notifications": {
    "enabled": true,
    "duration": 3000
  }
}
```

---

## 4. API Client Design

### 4.1 Client Interface

```typescript
// services/client.ts

interface MemoryClient {
  // Working Memory
  getOrCreateWorkingMemory(sessionId: string, namespace?: string): Promise<WorkingMemory>
  putWorkingMemory(sessionId: string, memory: WorkingMemory): Promise<void>
  setWorkingMemoryData(sessionId: string, data: Record<string, unknown>): Promise<void>
  
  // Long-term Memory
  createLongTermMemory(memories: MemoryRecord[]): Promise<CreateResponse>
  searchLongTermMemory(query: string, options?: SearchOptions): Promise<SearchResponse>
  getLongTermMemory(id: string): Promise<MemoryRecord>
  forgetLongTermMemories(policy: ForgetPolicy): Promise<ForgetResponse>
  
  // Utility
  searchMemoryTool(query: string, options?: SearchOptions): Promise<ToolSearchResponse>
}
```

### 4.2 API Endpoints Mapping

| Client Method | REST API Endpoint |
|---------------|-------------------|
| getOrCreateWorkingMemory | GET/POST /v1/working-memory/{session_id} |
| putWorkingMemory | PUT /v1/working-memory/{session_id} |
| setWorkingMemoryData | PUT /v1/working-memory/{session_id}/data |
| createLongTermMemory | POST /v1/long-term-memory |
| searchLongTermMemory | POST /v1/long-term-memory/search |
| getLongTermMemory | GET /v1/long-term-memory/{id} |
| forgetLongTermMemories | POST /v1/long-term-memory/forget |
| searchMemoryTool | POST /v1/memory/search-tool |

---

## 5. Hook Implementation Details

### 5.1 Event Hooks

```typescript
// hooks/session.ts

// Session lifecycle events to handle:
// - session.created: Initialize working memory association
// - session.idle: Trigger auto-capture after delay
// - session.compacted: Inject relevant memories
// - session.deleted: Flush working memory to long-term
```

### 5.2 Chat Message Hook

```typescript
// hooks/chat-message.ts

// On first message:
// 1. Search relevant memories (semantic search with query)
// 2. Search user profile memories
// 3. Search project memories
// 4. Format as [MEMORY] block
// 5. Inject into output.parts
```

### 5.3 Compaction Hook

```typescript
// hooks/compaction.ts

// Pre-compaction (experimental.session.compacting):
// 1. Search project memories
// 2. Inject context into output.context

// Post-compaction (session.compacted):
// 1. Search memories for this session
// 2. Format and inject for continuation
```

---

## 6. Task Breakdown

### Task 1: Project Setup

**Files:**
- Create: `.opencode/plugins/agent-memory/package.json`
- Create: `.opencode/plugins/agent-memory/index.ts`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "agent-memory",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {}
}
```

- [ ] **Step 2: Create index.ts with basic plugin structure**

```typescript
import type { Plugin, PluginInput } from "@opencode-ai/plugin"

export const AgentMemoryPlugin: Plugin = async (input: PluginInput) => {
  return {
    name: "agent-memory",
    // Hooks will be added here
  }
}
```

---

### Task 2: Configuration System

**Files:**
- Create: `.opencode/plugins/agent-memory/config.ts`
- Create: `.opencode/plugins/agent-memory/utils/jsonc.ts`
- Create: `.opencode/plugins/agent-memory/utils/secret-resolver.ts`

- [ ] **Step 1: Create JSONC parser utility**

```typescript
// utils/jsonc.ts
export function stripJsoncComments(content: string): string {
  // Implementation from opencode-mem/src/services/jsonc.ts
  // Handles // and /* comments, trailing commas
}
```

- [ ] **Step 2: Create secret resolver utility**

```typescript
// utils/secret-resolver.ts
export function resolveSecretValue(value: string | undefined): string | undefined {
  // "file://path" → read file
  // "env://VAR" → process.env.VAR
  // Otherwise return as-is
}
```

- [ ] **Step 3: Create config.ts with defaults and loading**

```typescript
// config.ts
interface AgentMemoryConfig {
  serverUrl: string
  apiKey?: string
  namespacePrefix: string
  chatMessage: {
    enabled: boolean
    injectOn: "first" | "always"
    maxMemories: number
    similarityThreshold: number
    searchMode: "semantic" | "keyword" | "hybrid"
    excludeCurrentSession: boolean
    maxAgeDays: number | null
  }
  compaction: {
    enabled: boolean
    injectBeforeCompaction: boolean
    injectAfterCompaction: boolean
    memoryLimit: number
  }
  autoCapture: {
    enabled: boolean
    idleDelayMs: number
    strategy: "discrete" | "summary"
    technicalOnly: boolean
  }
  tools: {
    enabled: boolean
    namePrefix: string
  }
  notifications: {
    enabled: boolean
    duration: number
  }
}

// Load from ~/.config/opencode/agent-memory.jsonc
// Support environment variable overrides
```

---

### Task 3: Type Definitions

**Files:**
- Create: `.opencode/plugins/agent-memory/types.ts`

- [ ] **Step 1: Define core types**

```typescript
// types.ts

export interface MemoryRecord {
  id: string
  text: string
  memory_type: "episodic" | "semantic" | "message"
  topics?: string[]
  entities?: string[]
  session_id?: string
  namespace?: string
  created_at: string
  updated_at: string
}

export interface WorkingMemory {
  session_id: string
  namespace?: string
  messages: MemoryMessage[]
  memories: MemoryRecord[]
  data?: Record<string, unknown>
  context?: string
}

export interface MemoryMessage {
  role: "user" | "assistant"
  content: string
  id: string
  created_at: string
}

export interface SearchOptions {
  namespace?: string
  topics?: string[]
  entities?: string[]
  session_id?: string
  limit?: number
  similarity_threshold?: number
  search_mode?: "semantic" | "keyword" | "hybrid"
  max_age_days?: number
}

export interface SearchResponse {
  memories: MemoryRecord[]
  total: number
}

export interface SessionState {
  sessionId: string
  createdAt: number
  isIdle: boolean
  lastActivity: number
  capturedMemoryIds: Set<string>
}
```

---

### Task 4: API Client

**Files:**
- Create: `.opencode/plugins/agent-memory/services/client.ts`

- [ ] **Step 1: Create MemoryAPIClient class**

```typescript
// services/client.ts

const DEFAULT_TIMEOUT_MS = 30000

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error(`Timeout after ${ms}ms`)), ms)
    )
  ])
}

export class MemoryAPIClient {
  private baseUrl: string
  private apiKey?: string

  constructor(config: { serverUrl: string; apiKey?: string }) {
    this.baseUrl = config.serverUrl.replace(/\/$/, "")
    this.apiKey = config.apiKey
  }

  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(this.apiKey && { Authorization: `Bearer ${this.apiKey}` })
    }

    const response = await withTimeout(
      fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers
      }),
      DEFAULT_TIMEOUT_MS
    )

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`)
    }

    return response.json()
  }

  async getOrCreateWorkingMemory(sessionId: string, namespace?: string): Promise<WorkingMemory> {
    return this.request(`/v1/working-memory/${sessionId}`, {
      method: "GET"
    })
  }

  async putWorkingMemory(sessionId: string, memory: WorkingMemory): Promise<void> {
    await this.request(`/v1/working-memory/${sessionId}`, {
      method: "PUT",
      body: JSON.stringify(memory)
    })
  }

  async searchLongTermMemory(query: string, options?: SearchOptions): Promise<SearchResponse> {
    return this.request("/v1/long-term-memory/search", {
      method: "POST",
      body: JSON.stringify({ text: query, ...options })
    })
  }

  async createLongTermMemory(memories: MemoryRecord[]): Promise<{ ids: string[] }> {
    return this.request("/v1/long-term-memory", {
      method: "POST",
      body: JSON.stringify({ memories })
    })
  }

  async searchMemoryTool(query: string, options?: SearchOptions): Promise<SearchResponse> {
    return this.request("/v1/memory/search-tool", {
      method: "POST",
      body: JSON.stringify({ query, ...options })
    })
  }
}
```

---

### Task 5: Session State Management

**Files:**
- Create: `.opencode/plugins/agent-memory/services/session.ts`

- [ ] **Step 1: Create session state manager**

```typescript
// services/session.ts

interface SessionState {
  opencodeSessionId: string
  createdAt: number
  lastActivity: number
  capturedMessageIds: Set<string>
  pendingPrompts: string[]
}

const sessions = new Map<string, SessionState>()

export function getOrCreateSession(opencodeSessionId: string): SessionState {
  let session = sessions.get(opencodeSessionId)
  if (!session) {
    session = {
      opencodeSessionId,
      createdAt: Date.now(),
      lastActivity: Date.now(),
      capturedMessageIds: new Set(),
      pendingPrompts: []
    }
    sessions.set(opencodeSessionId, session)
  }
  return session
}

export function updateSessionActivity(opencodeSessionId: string): void {
  const session = sessions.get(opencodeSessionId)
  if (session) {
    session.lastActivity = Date.now()
  }
}

export function deleteSession(opencodeSessionId: string): void {
  sessions.delete(opencodeSessionId)
}
```

---

### Task 6: Namespace/Tag Generation

**Files:**
- Create: `.opencode/plugins/agent-memory/services/tags.ts`

- [ ] **Step 1: Create namespace helpers**

```typescript
// services/tags.ts

import { createHash } from "node:crypto"
import { execSync } from "node:child_process"

export interface Tags {
  user: string
  project: string
}

function sha256(input: string): string {
  return createHash("sha256").update(input).digest("hex").slice(0, 16)
}

export function getUserNamespace(prefix: string): string {
  const email = execSync("git config user.email", { encoding: "utf-8" }).trim()
  return `${prefix}_user_${sha256(email || "anonymous")}`
}

export function getProjectNamespace(prefix: string, directory: string): string {
  return `${prefix}_project_${sha256(directory)}`
}

export function getTags(prefix: string, directory: string): Tags {
  return {
    user: getUserNamespace(prefix),
    project: getProjectNamespace(prefix, directory)
  }
}
```

---

### Task 7: Context Formatting

**Files:**
- Create: `.opencode/plugins/agent-memory/services/context.ts`

- [ ] **Step 1: Create context formatter**

```typescript
// services/context.ts

import type { MemoryRecord } from "../types.js"

export function formatContextForPrompt(
  memories: MemoryRecord[],
  options?: { maxMemories?: number; includeMetadata?: boolean }
): string {
  const maxMemories = options?.maxMemories ?? 5
  const parts: string[] = ["[MEMORY]"]

  const relevantMemories = memories.slice(0, maxMemories)

  if (relevantMemories.length > 0) {
    parts.push("\nRelevant Memories:")
    for (const mem of relevantMemories) {
      const date = new Date(mem.created_at).toLocaleDateString()
      const topics = mem.topics?.length ? ` [${mem.topics.join(", ")}]` : ""
      parts.push(`- [${date}]${topics} ${mem.text}`)
    }
  }

  if (parts.length === 1) {
    return ""
  }

  return parts.join("\n")
}

export function formatCompactionContext(memories: MemoryRecord[]): string {
  const parts: string[] = ["[COMPACTION MEMORY]"]

  if (memories.length > 0) {
    parts.push("\nSession Context:")
    for (const mem of memories) {
      parts.push(`- ${mem.text}`)
    }
  }

  return parts.join("\n")
}
```

---

### Task 8: Event Hooks Implementation

**Files:**
- Modify: `.opencode/plugins/agent-memory/index.ts`
- Create: `.opencode/plugins/agent-memory/hooks/session.ts`

- [ ] **Step 1: Create session event handler**

```typescript
// hooks/session.ts

import type { PluginInput } from "@opencode-ai/plugin"
import { getOrCreateSession, updateSessionActivity, deleteSession } from "../services/session.js"
import { CONFIG } from "../config.js"
import { memoryClient } from "../services/client.js"

let autoCaptureTimeout: NodeJS.Timeout | null = null

export function createSessionHooks(ctx: PluginInput) {
  return {
    async event({ event }: { event: { type: string; properties?: unknown } }) {
      const props = event.properties as Record<string, unknown> | undefined

      switch (event.type) {
        case "session.created": {
          const sessionId = props?.sessionID as string | undefined
          if (sessionId) {
            getOrCreateSession(sessionId)
          }
          break
        }

        case "session.idle": {
          const sessionId = props?.sessionID as string | undefined
          if (!sessionId || !CONFIG.autoCapture.enabled) break

          // Delay before auto-capture
          if (autoCaptureTimeout) {
            clearTimeout(autoCaptureTimeout)
          }
          autoCaptureTimeout = setTimeout(async () => {
            try {
              await performAutoCapture(ctx, sessionId)
            } catch (err) {
              console.error("[agent-memory] auto-capture failed:", err)
            }
          }, CONFIG.autoCapture.idleDelayMs)
          break
        }

        case "session.compacted": {
          if (!CONFIG.compaction.enabled || !CONFIG.compaction.injectAfterCompaction) break
          const sessionId = props?.sessionID as string | undefined
          if (sessionId) {
            await injectMemoriesAfterCompaction(ctx, sessionId)
          }
          break
        }

        case "session.deleted": {
          const sessionId = props?.sessionID as string | undefined
          if (sessionId) {
            deleteSession(sessionId)
          }
          break
        }

        case "message.updated": {
          const info = props?.info as { sessionID?: string } | undefined
          if (info?.sessionID) {
            updateSessionActivity(info.sessionID)
          }
          break
        }
      }
    }
  }
}

async function performAutoCapture(ctx: PluginInput, sessionId: string): Promise<void> {
  // Implementation: get messages, summarize, save to long-term memory
  // Similar to opencode-mem auto-capture but using agent-memory-server API
}

async function injectMemoriesAfterCompaction(ctx: PluginInput, sessionId: string): Promise<void> {
  // Search memories for this session, format, and inject
}
```

---

### Task 9: Chat Message Hook

**Files:**
- Create: `.opencode/plugins/agent-memory/hooks/chat-message.ts`

- [ ] **Step 1: Create chat message hook**

```typescript
// hooks/chat-message.ts

import type { PluginInput } from "@opencode-ai/plugin"
import { memoryClient } from "../services/client.js"
import { getTags } from "../services/tags.js"
import { formatContextForPrompt } from "../services/context.js"
import { CONFIG } from "../config.js"
import { getOrCreateSession } from "../services/session.js"

interface ChatMessageEvent {
  input: {
    parts: Array<{ type: string; text?: string }>
    isFirst?: boolean
  }
  output: {
    parts: Array<{ type: string; text?: string }>
  }
}

export function createChatMessageHook(ctx: PluginInput) {
  return {
    async "chat.message"(input: ChatMessageEvent, output: ChatMessageEvent) {
      if (!CONFIG.chatMessage.enabled) return
      if (CONFIG.chatMessage.injectOn === "first" && !input.isFirst) return

      const sessionId = ctx.client?.session?.id
      if (!sessionId) return

      const session = getOrCreateSession(sessionId)
      const tags = getTags(CONFIG.namespacePrefix, ctx.directory)

      // Build search query from conversation context
      const userParts = input.parts.filter(p => p.type === "text")
      const query = userParts.map(p => p.text).join(" ").slice(0, 500)

      if (!query.trim()) return

      // Search memories
      const searchOptions = {
        namespace: tags.project,
        limit: CONFIG.chatMessage.maxMemories,
        similarity_threshold: CONFIG.chatMessage.similarityThreshold,
        search_mode: CONFIG.chatMessage.searchMode,
        max_age_days: CONFIG.chatMessage.maxAgeDays ?? undefined,
        session_id: CONFIG.chatMessage.excludeCurrentSession ? undefined : sessionId
      }

      const results = await memoryClient.searchLongTermMemory(query, searchOptions)

      if (results.memories.length === 0) return

      // Format and inject
      const context = formatContextForPrompt(results.memories, {
        maxMemories: CONFIG.chatMessage.maxMemories
      })

      if (context) {
        output.parts.push({
          type: "text",
          text: context
        })
      }
    }
  }
}
```

---

### Task 10: Compaction Hook

**Files:**
- Create: `.opencode/plugins/agent-memory/hooks/compaction.ts`

- [ ] **Step 1: Create compaction hook**

```typescript
// hooks/compaction.ts

import type { PluginInput } from "@opencode-ai/plugin"
import { memoryClient } from "../services/client.js"
import { getTags } from "../services/tags.js"
import { formatCompactionContext } from "../services/context.js"
import { CONFIG } from "../config.js"

export function createCompactionHook(ctx: PluginInput) {
  return {
    "experimental.session.compacting": async (input: unknown, output: { context: string[] }) => {
      if (!CONFIG.compaction.enabled || !CONFIG.compaction.injectBeforeCompaction) return

      const sessionId = ctx.client?.session?.id
      if (!sessionId) return

      const tags = getTags(CONFIG.namespacePrefix, ctx.directory)

      // Search project memories
      const results = await memoryClient.searchLongTermMemory("", {
        namespace: tags.project,
        limit: CONFIG.compaction.memoryLimit,
        search_mode: "semantic"
      })

      if (results.memories.length === 0) return

      const context = formatCompactionContext(results.memories)
      if (context) {
        output.context.push(context)
      }
    }
  }
}
```

---

### Task 11: Memory Tool Definition

**Files:**
- Create: `.opencode/plugins/agent-memory/tools/memory.ts`

- [ ] **Step 1: Create memory tool**

```typescript
// tools/memory.ts

import { tool } from "@opencode-ai/plugin"
import { memoryClient } from "../services/client.js"
import { getTags } from "../services/tags.js"
import { formatContextForPrompt } from "../services/context.js"
import { CONFIG } from "../config.js"

const z = tool.schema

export function createMemoryTool(ctx: PluginInput) {
  const toolName = `${CONFIG.tools.namePrefix}_search`

  return {
    [toolName]: tool({
      description: "Search memories from agent-memory-server. Use this to find relevant past context, decisions, or information.",
      args: {
        query: z.string().describe("Search query for finding relevant memories"),
        mode: z.enum(["search", "add", "list", "get", "forget"]).optional().default("search"),
        namespace: z.string().optional().describe("Namespace to search in"),
        topics: z.array(z.string()).optional().describe("Filter by topics"),
        limit: z.number().optional().default(5).describe("Maximum results")
      },
      async execute(args, context) {
        const tags = getTags(CONFIG.namespacePrefix, context.directory)
        const searchNamespace = args.namespace || tags.project

        if (args.mode === "search") {
          const results = await memoryClient.searchLongTermMemory(args.query, {
            namespace: searchNamespace,
            topics: args.topics,
            limit: args.limit,
            similarity_threshold: CONFIG.chatMessage.similarityThreshold,
            search_mode: CONFIG.chatMessage.searchMode
          })

          return formatContextForPrompt(results.memories, { maxMemories: args.limit })
        }

        if (args.mode === "list") {
          const results = await memoryClient.searchLongTermMemory("", {
            namespace: searchNamespace,
            topics: args.topics,
            limit: args.limit
          })

          return formatContextForPrompt(results.memories, { maxMemories: args.limit })
        }

        return "Unknown mode"
      }
    })
  }
}
```

---

### Task 12: Main Plugin Integration

**Files:**
- Modify: `.opencode/plugins/agent-memory/index.ts`

- [ ] **Step 1: Integrate all hooks and tools**

```typescript
// index.ts (final)

import type { Plugin, PluginInput } from "@opencode-ai/plugin"
import { CONFIG, loadConfig } from "./config.js"
import { MemoryAPIClient, memoryClient } from "./services/client.js"
import { createSessionHooks } from "./hooks/session.js"
import { createChatMessageHook } from "./hooks/chat-message.js"
import { createCompactionHook } from "./hooks/compaction.js"
import { createMemoryTool } from "./tools/memory.js"

export const AgentMemoryPlugin: Plugin = async (input: PluginInput) => {
  // Load configuration
  loadConfig()

  // Initialize API client
  const apiClient = new MemoryAPIClient({
    serverUrl: CONFIG.serverUrl,
    apiKey: CONFIG.apiKey
  })

  // Inject client for use by hooks
  ;(input as any).memoryClient = apiClient

  // Build plugin
  return {
    name: "agent-memory",
    
    // Event hooks
    ...createSessionHooks(input),
    
    // Chat message hook
    ...createChatMessageHook(input),
    
    // Compaction hook
    ...createCompactionHook(input),
    
    // Custom tools
    tool: CONFIG.tools.enabled ? createMemoryTool(input) : {}
  }
}
```

---

### Task 13: README Documentation

**Files:**
- Create: `.opencode/plugins/agent-memory/README.md`

- [ ] **Step 1: Create README**

```markdown
# Agent Memory OpenCode Plugin

OpenCode plugin for persistent memory using agent-memory-server.

## Features

- **Automatic Context Injection**: Relevant memories injected into AI context
- **Compaction Support**: Pre/post compaction context handling
- **Auto-Capture**: Automatic memory extraction from conversations
- **Memory Tools**: search_memory, list_memory tools for explicit operations

## Installation

Add to `~/.config/opencode/opencode.json`:

```json
{
  "plugin": ["agent-memory"]
}
```

Create `~/.config/opencode/agent-memory.jsonc`:

```jsonc
{
  "serverUrl": "http://localhost:8000",
  "chatMessage": {
    "enabled": true,
    "injectOn": "first",
    "maxMemories": 5
  },
  "compaction": {
    "enabled": true,
    "injectBeforeCompaction": true,
    "injectAfterCompaction": true
  },
  "autoCapture": {
    "enabled": true,
    "idleDelayMs": 10000
  }
}
```

## Usage

The plugin automatically:
- Injects relevant memories on first message
- Captures memories on session idle
- Handles session compaction
- Provides memory tools

Manual tool usage:
```
memory_search({ query: "authentication setup" })
```
```

---

## 7. Implementation Notes

### 7.1 Dependencies

The plugin uses only built-in Node.js APIs:
- `fetch` for HTTP requests (built into Bun)
- `node:crypto` for hashing
- `node:child_process` for git config
- `node:fs` for file operations (if needed for logging)

### 7.2 Error Handling

All API calls should:
1. Use timeout wrapper
2. Catch and log errors
3. Not crash the plugin
4. Return sensible defaults on failure

### 7.3 Configuration Loading Order

1. Load from `~/.config/opencode/agent-memory.jsonc`
2. Load from `project/.opencode/agent-memory.jsonc` (if exists)
3. Merge (project overrides global)
4. Check environment variables for overrides:
   - `AGENT_MEMORY_SERVER_URL`
   - `AGENT_MEMORY_API_KEY`

### 7.4 Session State

Session state is kept in-memory only. For production, consider persisting:
- Session ↔ namespace mappings
- Captured message IDs
- Pending prompt queue

---

## 8. Testing Strategy

### 8.1 Manual Testing

1. Start agent-memory-server
2. Load plugin in OpenCode
3. Send first message → verify context injection
4. Wait for idle → verify auto-capture
5. Trigger compaction → verify compaction hooks
6. Use memory_search tool → verify API calls

### 8.2 Integration Points to Verify

- [ ] `session.created` → session state created
- [ ] `message.updated` → activity timestamp updated
- [ ] `session.idle` → auto-capture triggered after delay
- [ ] `session.compacted` → memories injected
- [ ] `session.deleted` → session state cleaned up
- [ ] `chat.message` → context injected on first message
- [ ] `experimental.session.compacting` → pre-compaction context added
- [ ] `memory_search` tool → returns formatted results

---

## 9. Future Enhancements (Out of Scope)

- Web UI for memory management
- Message buffering (race condition handling)
- Session mapping persistence
- OAuth authentication flow
- Multiple namespace support
- Memory analytics/dashboard

---

**Plan complete.** Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
