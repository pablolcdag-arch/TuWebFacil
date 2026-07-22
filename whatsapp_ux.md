# TuWebFacil - WhatsApp UX for Post-Sale Management

## Overview

The WhatsApp UX system provides clients with an intuitive interface to manage their websites through WhatsApp messages. It implements a state machine that guides users through different operations and maintains context throughout the conversation.

## State Machine Design

The state machine manages the conversation flow and keeps track of the client's current context. Each state represents a specific point in the conversation and determines how to interpret and respond to the client's messages.

### Core States

1. **IDLE**
   - Initial state when no active operation is in progress
   - Displays the main menu when triggered
   - Transitions to other states based on user selection

2. **MAIN_MENU**
   - Displays available options for website management
   - Options include: Blog, Gallery, Pricing, Contact Info, SEO, etc.
   - Transitions to specific section states based on user selection

3. **SECTION_MENU**
   - Displays options for a specific section (Blog, Gallery, etc.)
   - Options include: View, Add, Edit, Delete
   - Transitions to operation states based on user selection

4. **VIEWING**
   - Displays current content for the selected section
   - Provides navigation options for multi-item sections
   - Returns to SECTION_MENU when complete

5. **ADDING**
   - Guides user through adding new content
   - Collects required information step by step
   - Returns to SECTION_MENU when complete

6. **EDITING**
   - Guides user through editing existing content
   - Shows current values and collects new values
   - Returns to SECTION_MENU when complete

7. **DELETING**
   - Confirms deletion of content
   - Executes deletion if confirmed
   - Returns to SECTION_MENU when complete

8. **CONFIRMATION**
   - Asks for confirmation before making changes
   - Transitions to appropriate state based on confirmation
   - Implements undo functionality if needed

9. **HELP**
   - Provides context-sensitive help based on current state
   - Returns to previous state when complete

10. **ERROR**
    - Handles unexpected inputs or system errors
    - Provides guidance to return to a valid state
    - May transition to HELP state

### State Transitions

```
IDLE → MAIN_MENU → SECTION_MENU → OPERATION_STATE → CONFIRMATION → SECTION_MENU
  ↑                     ↑              ↑                  ↑
  |                     |              |                  |
  └─────────────────────┴──────────────┴──────────────────┘
                        (Cancel/Back operations)
```

## Menu Structure

### Main Menu

```
📱 TuWebFacil - Panel de Control

Selecciona una opción:
1️⃣ Blog
2️⃣ Galería
3️⃣ Precios
4️⃣ Información de Contacto
5️⃣ SEO
6️⃣ Configuración
7️⃣ Ayuda
```

### Section Menu (Example: Blog)

```
📝 Gestión del Blog

Selecciona una opción:
1️⃣ Ver artículos
2️⃣ Agregar artículo
3️⃣ Editar artículo
4️⃣ Eliminar artículo
5️⃣ Volver al menú principal
```

### Operation Flow (Example: Add Blog Post)

```
🆕 Nuevo Artículo del Blog

Paso 1: Envía el título del artículo
> [User sends title]

Paso 2: Envía el contenido del artículo
> [User sends content]

Paso 3: Envía una imagen para el artículo (opcional)
> [User sends image or skips]

✅ Artículo creado con éxito!
¿Deseas publicarlo ahora?
1️⃣ Sí, publicar ahora
2️⃣ No, guardar como borrador
```

## Undo Functionality

The system implements an "Undo" feature that allows clients to revert recent changes, providing confidence that they won't permanently break their website.

### Undo Implementation

1. **History Tracking**
   - Each content modification is recorded in the `content_history` table
   - Records include previous state, change description, and timestamp

2. **Undo Command**
   - Available after any modification operation
   - Displays recent changes that can be undone
   - Example: "Para deshacer el último cambio, escribe 'Deshacer'"

3. **Undo Confirmation**
   - Confirms the specific change to be undone
   - Provides before/after preview when possible
   - Executes the undo operation when confirmed

4. **Undo Limitations**
   - Time-limited (e.g., changes within the last 24 hours)
   - Some operations may not be undoable (clearly marked)
   - Sequential undos supported (can undo multiple changes in reverse order)

### Undo Example Flow

```
✅ Artículo "10 Tips de SEO" eliminado con éxito.
Para deshacer esta acción, escribe "Deshacer".

> Deshacer

🔄 Confirmación: ¿Deseas recuperar el artículo "10 Tips de SEO"?
1️⃣ Sí, recuperar artículo
2️⃣ No, mantener eliminado

> 1

✅ ¡Artículo recuperado con éxito!
```

## Implementation Details

### Message Processing Flow

1. **Receive Message**
   - WhatsApp webhook receives client message
   - Message is logged in `whatsapp_interactions` table

2. **Context Retrieval**
   - System retrieves client's current state and context
   - Loads relevant data based on context

3. **Intent Detection**
   - Uses Gemini AI to analyze message intent
   - Maps intent to appropriate state transition

4. **State Processing**
   - Executes logic for current state
   - Prepares response based on state and intent

5. **Response Generation**
   - Formats response according to current context
   - May include buttons, lists, or media

6. **Send Response**
   - Sends formatted response via WhatsApp API
   - Updates client's state and context in database

### Code Structure

The WhatsApp UX system will be implemented in the following files:

1. **whatsapp_state_machine.py**
   - Defines the state machine class and states
   - Handles state transitions and context management

2. **whatsapp_handlers.py**
   - Implements handlers for different states
   - Contains business logic for each operation

3. **whatsapp_templates.py**
   - Defines message templates for different states
   - Formats responses with appropriate structure

4. **whatsapp_undo.py**
   - Implements the undo functionality
   - Manages history tracking and restoration

## Integration with Website Content Management

The WhatsApp UX system integrates with the website content management system to make real-time changes to client websites.

### Content Update Process

1. Client sends a content update request via WhatsApp
2. System validates the request and confirms with the client
3. Upon confirmation, system:
   - Creates a backup of current content in `content_history`
   - Updates the content in `website_content`
   - Regenerates the website HTML if needed
   - Sends confirmation to the client

### Content Validation

To ensure website integrity, the system validates all content updates:

1. Text content is checked for appropriate length and format
2. Images are processed to ensure proper size and format
3. Structural changes are validated against the template requirements
4. SEO elements are checked for best practices

## Example Implementation: whatsapp_state_machine.py

```python
from enum import Enum, auto
import json
from datetime import datetime
import google.generativeai as genai
from supabase import create_client, Client
import os

# State definitions
class State(Enum):
    IDLE = auto()
    MAIN_MENU = auto()
    SECTION_MENU = auto()
    VIEWING = auto()
    ADDING = auto()
    EDITING = auto()
    DELETING = auto()
    CONFIRMATION = auto()
    HELP = auto()
    ERROR = auto()

class WhatsAppStateMachine:
    def __init__(self, supabase_client, gemini_model):
        self.supabase = supabase_client
        self.gemini = gemini_model
        
    def process_message(self, client_id, message_text, message_type="text"):
        """
        Process an incoming WhatsApp message and return the appropriate response.
        """
        # Get client's current state and context
        client_state = self._get_client_state(client_id)
        
        # Detect intent using Gemini
        intent = self._detect_intent(message_text, client_state)
        
        # Process based on current state
        new_state, response = self._process_state(client_id, client_state, message_text, intent)
        
        # Update client state in database
        self._update_client_state(client_id, new_state)
        
        # Log interaction
        self._log_interaction(client_id, message_text, "incoming", client_state, new_state, intent)
        
        return response
    
    def _get_client_state(self, client_id):
        """
        Retrieve the client's current state and context from the database.
        """
        try:
            result = self.supabase.table("whatsapp_interactions") \
                .select("current_state, context") \
                .eq("client_id", client_id) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            if result.data and len(result.data) > 0:
                current_state = State[result.data[0]["current_state"]]
                context = json.loads(result.data[0]["context"]) if result.data[0]["context"] else {}
                return {"state": current_state, "context": context}
            else:
                # New client, initialize state
                return {"state": State.IDLE, "context": {}}
                
        except Exception as e:
            print(f"Error retrieving client state: {e}")
            return {"state": State.ERROR, "context": {}}
    
    def _detect_intent(self, message_text, client_state):
        """
        Use Gemini to detect the intent of the message based on current state.
        """
        try:
            prompt = f"""
            Analyze this WhatsApp message from a website client and determine their intent.
            
            Current state: {client_state['state'].name}
            Current context: {json.dumps(client_state['context'])}
            
            Message: "{message_text}"
            
            Return a JSON object with:
            1. "intent": The primary intent (MENU_SELECT, VIEW, ADD, EDIT, DELETE, HELP, CANCEL, UNDO, CONFIRM, OTHER)
            2. "parameters": Any parameters extracted (e.g., selection number, content values)
            3. "confidence": Confidence score from 0-1
            """
            
            response = self.gemini.generate_content(prompt)
            intent_data = json.loads(response.text)
            return intent_data
            
        except Exception as e:
            print(f"Error detecting intent: {e}")
            return {"intent": "ERROR", "parameters": {}, "confidence": 0}
    
    def _process_state(self, client_id, client_state, message_text, intent):
        """
        Process the message based on current state and detected intent.
        Returns the new state and response message.
        """
        current_state = client_state["state"]
        context = client_state["context"]
        
        # Handle global commands
        if intent["intent"] == "HELP":
            return State.HELP, self._generate_help_message(current_state, context)
        
        if intent["intent"] == "CANCEL":
            return self._handle_cancel(current_state, context)
        
        if intent["intent"] == "UNDO":
            return self._handle_undo(client_id, context)
        
        # State-specific processing
        if current_state == State.IDLE:
            return self._handle_idle_state(intent, context)
        
        elif current_state == State.MAIN_MENU:
            return self._handle_main_menu(intent, context)
        
        elif current_state == State.SECTION_MENU:
            return self._handle_section_menu(intent, context)
        
        elif current_state == State.VIEWING:
            return self._handle_viewing(intent, context)
        
        elif current_state == State.ADDING:
            return self._handle_adding(client_id, intent, context, message_text)
        
        elif current_state == State.EDITING:
            return self._handle_editing(client_id, intent, context, message_text)
        
        elif current_state == State.DELETING:
            return self._handle_deleting(client_id, intent, context)
        
        elif current_state == State.CONFIRMATION:
            return self._handle_confirmation(client_id, intent, context)
        
        elif current_state == State.HELP:
            # Return to previous state after help
            return context.get("previous_state", State.MAIN_MENU), self._generate_main_menu()
        
        else:  # ERROR or unknown state
            return State.MAIN_MENU, self._generate_main_menu()
    
    def _update_client_state(self, client_id, new_state):
        """
        Update the client's state in the database.
        """
        try:
            self.supabase.table("whatsapp_interactions") \
                .update({"current_state": new_state["state"].name, "context": json.dumps(new_state["context"])}) \
                .eq("client_id", client_id) \
                .execute()
        except Exception as e:
            print(f"Error updating client state: {e}")
    
    def _log_interaction(self, client_id, message, direction, old_state, new_state, intent):
        """
        Log the interaction in the database.
        """
        try:
            self.supabase.table("whatsapp_interactions").insert({
                "client_id": client_id,
                "message": message,
                "direction": direction,
                "previous_state": old_state["state"].name,
                "current_state": new_state["state"].name,
                "intent": intent["intent"],
                "context": json.dumps(new_state["context"]),
                "created_at": datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            print(f"Error logging interaction: {e}")
    
    # State handler methods would be implemented here
    # Each would handle the specific logic for that state
    
    def _generate_main_menu(self):
        """
        Generate the main menu message.
        """
        return """
        📱 TuWebFacil - Panel de Control

        Selecciona una opción:
        1️⃣ Blog
        2️⃣ Galería
        3️⃣ Precios
        4️⃣ Información de Contacto
        5️⃣ SEO
        6️⃣ Configuración
        7️⃣ Ayuda
        """
    
    # Additional helper methods would be implemented here
```

## Example Implementation: whatsapp_undo.py

```python
import json
from datetime import datetime, timedelta

class UndoManager:
    def __init__(self, supabase_client):
        self.supabase = supabase_client
    
    def record_change(self, website_content_id, previous_content, change_description, changed_by):
        """
        Record a content change for potential undo.
        """
        try:
            self.supabase.table("content_history").insert({
                "website_content_id": website_content_id,
                "previous_content": json.dumps(previous_content),
                "change_description": change_description,
                "changed_by": changed_by,
                "can_revert": True,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            return True
        except Exception as e:
            print(f"Error recording change: {e}")
            return False
    
    def get_recent_changes(self, client_id, hours=24):
        """
        Get recent changes that can be undone for a client.
        """
        try:
            # Get client's websites
            websites_result = self.supabase.table("websites") \
                .select("id") \
                .eq("client_id", client_id) \
                .execute()
            
            if not websites_result.data:
                return []
            
            website_ids = [w["id"] for w in websites_result.data]
            
            # Get website content IDs
            content_result = self.supabase.table("website_content") \
                .select("id") \
                .in_("website_id", website_ids) \
                .execute()
            
            if not content_result.data:
                return []
            
            content_ids = [c["id"] for c in content_result.data]
            
            # Get recent history for these content IDs
            since_time = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
            history_result = self.supabase.table("content_history") \
                .select("*") \
                .in_("website_content_id", content_ids) \
                .eq("can_revert", True) \
                .gt("created_at", since_time) \
                .order("created_at", desc=True) \
                .execute()
            
            return history_result.data
        
        except Exception as e:
            print(f"Error getting recent changes: {e}")
            return []
    
    def undo_change(self, history_id):
        """
        Undo a specific change by restoring previous content.
        """
        try:
            # Get the history entry
            history_result = self.supabase.table("content_history") \
                .select("*") \
                .eq("id", history_id) \
                .execute()
            
            if not history_result.data:
                return False, "History entry not found"
            
            history = history_result.data[0]
            
            # Get current content
            content_result = self.supabase.table("website_content") \
                .select("*") \
                .eq("id", history["website_content_id"]) \
                .execute()
            
            if not content_result.data:
                return False, "Content not found"
            
            current_content = content_result.data[0]
            
            # Record the current state before undoing
            self.record_change(
                history["website_content_id"],
                current_content["content"],
                f"Auto-saved before undoing: {history['change_description']}",
                "system_undo"
            )
            
            # Restore the previous content
            previous_content = json.loads(history["previous_content"])
            
            self.supabase.table("website_content") \
                .update({"content": previous_content}) \
                .eq("id", history["website_content_id"]) \
                .execute()
            
            # Mark the history entry as used
            self.supabase.table("content_history") \
                .update({"can_revert": False}) \
                .eq("id", history_id) \
                .execute()
            
            return True, "Change successfully undone"
            
        except Exception as e:
            print(f"Error undoing change: {e}")
            return False, f"Error: {str(e)}"
```

## Security and Validation

### Client Authentication

1. **Phone Number Verification**
   - Clients are identified by their WhatsApp phone number
   - System verifies the phone number against registered clients

2. **Session Management**
   - Each conversation maintains a session context
   - Inactive sessions expire after a set period

### Input Validation

1. **Text Content**
   - Length limits appropriate to the content type
   - Filtering of potentially harmful content

2. **Media Content**
   - Size and format validation
   - Virus/malware scanning
   - Automatic resizing for web optimization

3. **Command Validation**
   - Verification that commands are valid for current state
   - Protection against command injection

## Performance Considerations

1. **Response Time**
   - Aim for sub-second response time for menu navigation
   - Content operations may take longer but should provide feedback

2. **Concurrency**
   - System handles multiple clients simultaneously
   - State is maintained separately for each client

3. **Error Recovery**
   - Automatic recovery from interrupted operations
   - Periodic state synchronization

## Future Enhancements

1. **Rich Media Support**
   - Enhanced image editing capabilities
   - Video content management
   - Document uploads

2. **Advanced Analytics**
   - Usage statistics for WhatsApp management
   - Most common operations
   - Error rate tracking

3. **Personalization**
   - Learning from client behavior
   - Suggesting common operations
   - Customizable menu options

4. **Integration with Other Channels**
   - Consistent experience across WhatsApp, Telegram, and web dashboard
   - State synchronization between channels