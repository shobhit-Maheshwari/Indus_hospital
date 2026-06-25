# PhiloAgents — Full System Sequence Diagram

Two main flows are documented here:
1. **Game Boot & Asset Loading** — how the UI starts up
2. **Player Conversation with a Philosopher** — the core interaction path, including the LangGraph agent pipeline

---

## Flow 1: Game Boot & Asset Loading

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant main.js
    participant Preloader
    participant MainMenu

    User->>Browser: Opens http://localhost:8080
    Browser->>main.js: Load & execute bundle
    main.js->>main.js: Create Phaser.Game(config)<br/>[width:1024, height:768, Arcade Physics]
    main.js->>Preloader: Launch first scene

    Note over Preloader: preload() runs
    Preloader->>Browser: load background image (talking_philosophers.jpg)
    Preloader->>Browser: load logo.png
    Preloader->>Browser: load tilesets (tuxmon, greece, plant)
    Preloader->>Browser: load tilemap JSON (philoagents-town.json)
    Preloader->>Browser: load 14 character atlases<br/>(sophia, socrates, plato, ... krishna)
    Browser-->>Preloader: All assets loaded

    Preloader->>MainMenu: scene.start('MainMenu')
    MainMenu->>User: Render title screen<br/>[Let's Play! | Instructions | Support]
```

---

## Flow 2: Player Starts the Game

```mermaid
sequenceDiagram
    actor User
    participant MainMenu
    participant Game as "Game.js (Scene)"
    participant Character
    participant DialogueBox
    participant DialogueManager

    User->>MainMenu: Click "Let's Play!"
    MainMenu->>Game: scene.start('Game')

    Note over Game: create() runs
    Game->>Game: createTilemap() — parse philoagents-town.json
    Game->>Game: addTileset() — attach 3 tilesets
    Game->>Game: createLayers() — Below/World/Above layers<br/>worldLayer.setCollisionByProperty()

    loop For each of 13 philosophers
        Game->>Character: new Character(scene, config)<br/>[id, name, spawnPoint, atlas, roamRadius]
        Character->>Character: create physics sprite
        Character->>Character: createAnimations() — 4-direction walk anims
        Character->>Character: createNameLabel() — floating name tag
        Character->>Character: startRoaming() — begin NPC AI movement
    end

    Game->>Game: setupPlayer() — spawn Sophia at "Spawn Point"
    Game->>Game: createPlayerAnimations() — 4-direction walk anims
    Game->>Game: setupCamera() — camera follows Sophia
    Game->>Game: setupControls() — bind arrow keys + ESC
    Game->>DialogueBox: new DialogueBox(scene) — invisible chat panel
    Game->>DialogueManager: new DialogueManager(scene)
    DialogueManager->>DialogueManager: setupKeyboardListeners()

    Game->>User: World visible, Sophia can walk
```

---

## Flow 3: NPC Roaming (Every Frame)

```mermaid
sequenceDiagram
    participant Game
    participant Character

    loop Every game frame (update loop)
        Game->>Character: philosopher.update(player, isInDialogue)

        alt Player is nearby AND in dialogue
            Character->>Character: setVelocity(0) — stop moving
            Character->>Character: facePlayer(player) — rotate sprite
            Character->>Character: cancelMovementTimer()
        else Player is nearby, no dialogue
            Character->>Character: setVelocity(0) — stop, face player
        else Player is far away
            Character->>Character: moveInCurrentDirection()
            Character->>Character: check roamRadius boundary
            Note over Character: If too far from spawn,<br/>steer back automatically
            alt movementTimer expired
                Character->>Character: chooseNewDirection()<br/>[40% walk, 60% pause]
            end
        end

        Character->>Character: updateNameLabelPosition()
    end
```

---

## Flow 4: Player Walks Up & Starts Dialogue (SPACE key)

```mermaid
sequenceDiagram
    actor User
    participant Game
    participant Character as "Character (NPC)"
    participant DialogueManager
    participant DialogueBox

    User->>Game: Press SPACE near Socrates
    Game->>Game: checkPhilosopherInteraction()
    Game->>Character: isPlayerNearby(player) → true

    alt DialogueBox not visible
        Game->>DialogueManager: startDialogue(philosopher)
        DialogueManager->>DialogueManager: set activePhilosopher = Socrates
        DialogueManager->>DialogueManager: isTyping = true
        DialogueManager->>DialogueBox: show("|") — show cursor prompt
        DialogueManager->>DialogueManager: startCursorBlink()<br/>[blinks every 300ms]
    end

    Character->>Character: facePlayer(player) — Socrates looks at Sophia
    Game->>User: Dialogue box visible with blinking cursor
```

---

## Flow 5: User Types & Sends a Message (WebSocket Path)

```mermaid
sequenceDiagram
    actor User
    participant DialogueManager
    participant DialogueBox
    participant WSService as "WebSocketApiService"
    participant FastAPI as "FastAPI /ws/chat"
    participant GenResponse as "get_streaming_response()"
    participant LangGraph as "LangGraph Workflow Graph"
    participant MongoDB as "MongoDB (Checkpointer)"
    participant LLM as "LLM (Groq/OpenAI)"

    User->>DialogueManager: Type characters (keydown events)
    DialogueManager->>DialogueManager: currentMessage += key
    DialogueManager->>DialogueBox: show(currentMessage + "|")

    User->>DialogueManager: Press ENTER
    DialogueManager->>DialogueBox: show("...") — waiting indicator
    DialogueManager->>DialogueManager: stopCursorBlink()

    Note over DialogueManager: activePhilosopher has no defaultMessage<br/>→ use WebSocket path

    DialogueManager->>WSService: processWebSocketMessage()
    WSService->>FastAPI: WebSocket connect → ws://localhost:8000/ws/chat
    FastAPI-->>WSService: Connection accepted

    WSService->>FastAPI: send JSON {message, philosopher_id}

    FastAPI->>FastAPI: PhilosopherFactory.get_philosopher(id)<br/>[load name, perspective, style]
    FastAPI->>GenResponse: get_streaming_response(message, philosopher_id, ...)

    GenResponse->>MongoDB: AsyncMongoDBSaver.from_conn_string()<br/>[open checkpointer connection]
    GenResponse->>LangGraph: graph_builder.compile(checkpointer)
    GenResponse->>LangGraph: graph.astream(input, config, stream_mode="messages")

    Note over LangGraph: LangGraph Workflow begins
    LangGraph->>LangGraph: START → conversation_node

    LangGraph->>LLM: get_philosopher_response_chain().ainvoke()<br/>[system prompt with philosopher persona + summary]
    LLM-->>LangGraph: AIMessage (may include tool_call for RAG)

    alt LLM decides to use retriever tool
        LangGraph->>LangGraph: tools_condition → "retrieve_philosopher_context"
        LangGraph->>MongoDB: vector search (long-term memory collection)
        MongoDB-->>LangGraph: top-K relevant document chunks
        LangGraph->>LangGraph: summarize_context_node<br/>[compress retrieved docs with LLM]
        LangGraph->>LangGraph: back to conversation_node
        LangGraph->>LLM: re-invoke chain with RAG context injected
        LLM-->>LangGraph: Final AIMessage response
    else LLM responds directly
        LangGraph->>LangGraph: tools_condition → connector_node
    end

    LangGraph->>LangGraph: connector_node → should_summarize_conversation?

    alt Message count exceeds threshold
        LangGraph->>LangGraph: summarize_conversation_node<br/>[summarize & prune old messages]
        LangGraph->>MongoDB: checkpoint.put() — save state
        LangGraph->>LangGraph: END
    else Under threshold
        LangGraph->>MongoDB: checkpoint.put() — save state
        LangGraph->>LangGraph: END
    end

    loop For each AIMessageChunk from conversation_node
        GenResponse-->>FastAPI: yield chunk (token/word)
        FastAPI->>WSService: send_json({"chunk": chunk})
        WSService->>DialogueManager: onChunk(chunk) callback
        DialogueManager->>DialogueManager: streamingText += chunk
        DialogueManager->>DialogueBox: show(streamingText) — live update
    end

    FastAPI->>WSService: send_json({"response": fullResponse, "streaming": false})
    WSService->>DialogueManager: onStreamingEnd() callback
    DialogueManager->>DialogueManager: finishStreaming() — isStreaming = false
    DialogueManager->>DialogueManager: schedule disconnect in 5 seconds
    DialogueManager->>User: Full philosopher response visible in dialogue box
```

---

## Flow 6: Fallback Path (REST API if WebSocket fails)

```mermaid
sequenceDiagram
    participant DialogueManager
    participant ApiService as "ApiService (HTTP)"
    participant FastAPI as "FastAPI POST /chat"
    participant GenResponse as "get_response()"
    participant LangGraph

    DialogueManager->>ApiService: fallbackToRegularApi()
    ApiService->>FastAPI: POST /chat {message, philosopher_id}
    FastAPI->>GenResponse: get_response(...)
    GenResponse->>LangGraph: graph.ainvoke(input, config)
    LangGraph-->>GenResponse: output_state (full response at once)
    GenResponse-->>FastAPI: last_message.content
    FastAPI-->>ApiService: {response: "..."}
    ApiService-->>DialogueManager: full text string

    DialogueManager->>DialogueManager: streamText(text, speed=30)<br/>[typewriter effect, char by char]
    DialogueManager->>DialogueManager: User sees gradual text reveal
```

---

## Flow 7: Pause Menu & Reset Game

```mermaid
sequenceDiagram
    actor User
    participant Game
    participant PauseMenu
    participant ApiService as "ApiService"
    participant FastAPI as "FastAPI POST /reset-memory"
    participant MongoDB

    User->>Game: Press ESC (no dialogue open)
    Game->>Game: scene.pause()
    Game->>PauseMenu: scene.launch('PauseMenu')
    PauseMenu->>User: Show overlay — Resume | Main Menu | Reset Game

    alt User clicks "Resume Game"
        User->>PauseMenu: Click Resume
        PauseMenu->>Game: scene.resume('Game')
        PauseMenu->>PauseMenu: scene.stop()

    else User clicks "Main Menu"
        User->>PauseMenu: Click Main Menu
        PauseMenu->>Game: scene.stop('Game')
        PauseMenu->>PauseMenu: scene.start('MainMenu')

    else User clicks "Reset Game"
        User->>PauseMenu: Click Reset Game
        PauseMenu->>ApiService: ApiService.resetMemory()
        ApiService->>FastAPI: POST /reset-memory
        FastAPI->>MongoDB: drop checkpoint collection
        FastAPI->>MongoDB: drop writes collection
        MongoDB-->>FastAPI: OK
        FastAPI-->>ApiService: {result: "success"}
        ApiService-->>PauseMenu: resolved

        PauseMenu->>Game: scene.stop('Game')
        PauseMenu->>Game: scene.start('Game') — fresh state
        PauseMenu->>PauseMenu: scene.stop()
    end
```

---

## Flow 8: Long-Term Memory Population (Offline / Startup)

```mermaid
sequenceDiagram
    participant Script as "Data Pipeline Script"
    participant LTMCreator as "LongTermMemoryCreator"
    participant Splitter as "TextSplitter"
    participant EmbedModel as "HuggingFace Embeddings"
    participant MongoDB as "MongoDB Vector Store"
    participant MongoIndex as "MongoIndex (Hybrid)"

    Script->>LTMCreator: build_from_settings()
    LTMCreator->>EmbedModel: get_embedding_model(model_id, device)
    LTMCreator->>Splitter: get_splitter(chunk_size)

    Script->>LTMCreator: __call__(philosophers list)
    LTMCreator->>MongoDB: clear_collection() — wipe old vectors

    loop For each philosopher
        LTMCreator->>Script: get_extraction_generator() → docs
        LTMCreator->>Splitter: split_documents(docs) → chunks
        LTMCreator->>LTMCreator: deduplicate_documents(chunks, threshold=0.7)
        LTMCreator->>EmbedModel: embed chunks
        EmbedModel-->>LTMCreator: embedding vectors
        LTMCreator->>MongoDB: vectorstore.add_documents(chunked_docs)
    end

    LTMCreator->>MongoIndex: create(is_hybrid=True, embedding_dim=...)
    MongoIndex->>MongoDB: create vector search index
    MongoDB-->>Script: Long-term memory ready for RAG queries
```
