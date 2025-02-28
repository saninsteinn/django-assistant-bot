# Django Assistant Bot

Django Assistant Bot is a framework for developing assistant bots powered by Django. The project includes modules for dialog management, AI service integration, and RAG (Retrieval-Augmented Generation), providing accurate answers based on uploaded documents. The structure features a custom admin interface, asynchronous dialog processing, and a FastAPI service for efficient ML model operations. The project architecture focuses on modularity and extensibility for building intelligent assistant solutions.

## Overview

The Django Assistant Bot project is organized into several key components that streamline the development of a sophisticated assistant bot.

1. **Assistant Module**: This core module encompasses essential functionalities, including a custom admin interface for managing user interactions and tokens, and an AI integration component that handles dialog management and response generation. It also features middleware for dynamic request handling and a robust document processing system, utilizing asynchronous programming to enhance performance and responsiveness.

2. **Example Module**: Serving as a practical demonstration, this module includes configuration files and task management setups that showcase the bot's capabilities. It provides a template for users to implement and configure their own instances of the assistant bot.

3. **GPU Service**: Built on FastAPI, this service is dedicated to processing machine learning models. It includes endpoints for generating embeddings and handling dialog responses, leveraging GPU resources for optimized performance. The architecture ensures efficient model management and error handling, enhancing the overall reliability of AI interactions.

4. **Testing Module**: This module is crucial for maintaining the integrity of the application, featuring a comprehensive suite of tests that cover CRUD operations and the core logic of the assistant bot. Utilizing pytest fixtures and factories, it promotes code reuse and ensures consistent testing across various components, thereby enhancing the robustness of the application.

Overall, the project exemplifies a modular architecture, promoting maintainability and scalability while ensuring a seamless user experience through efficient interactions and extensive testing.

## Key Features

- **Comprehensive Admin Interface**: A customized admin interface that enhances user management and optimizes interaction capabilities through tailored token management.

- **Asynchronous Dialog Management**: Efficient handling of multiple user interactions simultaneously, allowing for responsive and real-time communication with the assistant bot using advanced asynchronous programming techniques.

- **AI Integration**: Seamless integration with AI services for dialog processing and response generation, providing intelligent and context-aware interactions.

- **Robust Document Processing**: Background task management for document handling, ensuring efficient processing and retrieval of information.

- **Modular Architecture**: Clear separation of concerns across various modules, including dedicated components for loading data from external sources, processing documents, and managing user dialogs.

- **FastAPI-based GPU Service**: A dedicated service for processing machine learning models, offering optimized endpoint access for embedding generation and dialog responses, significantly enhancing AI capabilities.

- **Retrieval-Augmented Generation (RAG)**: Implementation of the RAG architecture that combines document retrieval with language model generation, allowing the bot to provide answers based on specific knowledge bases and documents. This enhances response accuracy and relevance by grounding answers in factual information.

- **Demonstrative Example Module**: A practical directory containing configurations and implementations that showcase the bot's features and serve as a template for user customization.

- **Comprehensive Testing Suite**: An extensive set of tests that ensures the reliability and integrity of all functionalities, leveraging pytest fixtures and utilities to promote code quality.

## System Requirements

To successfully run the Django Assistant Bot project, ensure your system meets the following requirements and dependencies:

- **Python**: Version 3.8 or higher.
- **Django**: Version 4.2.13, serving as the primary web framework.
- **Django REST Framework**: Version 3.15.1, for building RESTful APIs, essential for backend communication.
- **Celery**: Version 5.4.0, for managing asynchronous task queues, facilitating background processing.
- **Database**: PostgreSQL (recommended) with pgvector extension for vector similarity search.
- **Message Broker**: Redis (recommended) for task queuing with Celery.
- **AI Models**: Support for various LLM providers including OpenAI, Groq, and Ollama.

### Additional Dependencies

The project also includes various libraries to enhance functionality:
- **psycopg2-binary**: PostgreSQL adapter for Python.
- **python-telegram-bot**: For integrating Telegram messaging capabilities.
- **drf-yasg**: For generating OpenAPI specifications for the Django REST API.
- **django-filter**: Enhances API capabilities by allowing filtering of querysets.
- **pytest**: A testing framework that supports effective unit and integration testing.
- **markdown2** and **beautifulsoup4**: For document processing and text extraction.
- **fuzzywuzzy** and **python-Levenshtein**: For text similarity and fuzzy matching.

### Installation

Install the project and all its dependencies using:

```bash
pip install .
```

This will install the Django Assistant Bot package and all required dependencies from the setup.py file.

Alternatively, you can install the dependencies directly using the requirements.txt file:

```bash
pip install -r requirements.txt
```

Ensure that any additional system-specific dependencies are satisfied for optimal performance.

## Installation Guide

To set up the Django Assistant Bot project, follow these steps:

1. **Clone the Repository**: Begin by cloning the project repository to your local machine:
   
   ```bash
   git clone https://github.com/your_username/django-assistant-bot.git
   cd django-assistant-bot
   ```

2. **Create a Virtual Environment** (optional but recommended): It is a good practice to use a virtual environment to manage dependencies for your project:
   
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Requirements**: Install the project and its dependencies:
   
   ```bash
   pip install .
   ```
   
   This will install the Django Assistant Bot package and all required dependencies.

4. **Configure Environment Variables**: Set up environment variables necessary for the application. You can create a `.env` file in the root directory based on the provided `.env.example` and configure it according to your needs. Key variables include database connection settings, AI model configurations, and service endpoints.
   
5. **Run Migrations**: Apply database migrations to set up the necessary tables:
   
   ```bash
   python manage.py migrate
   ```

6. **Start the Development Server**: You can now run the application using the following command:
   
   ```bash
   python manage.py runserver
   ```

7. **Access the Application**: Open your web browser and navigate to the application URL to access the Django Assistant Bot interface.

8. **Test the Setup**: Optionally, run the test suite to ensure everything is functioning as expected:
   
   ```bash
   pytest
   ```

Following these steps will set up the Django Assistant Bot project on your system, enabling you to develop and test its functionalities smoothly.

## Usage Guide

The Django Assistant Bot project provides various functionalities for developing and interacting with a chatbot powered by Django and FastAPI. Below are examples of how to use the core features of the project:

### Starting the Server
After completing the installation, you can start the Django development server to interact with the application:
```bash
python manage.py runserver
```
Visit the server URL in your web browser to access the assistant bot interface.

### Interacting with the Bot
Once the server is running, you can interact with the assistant bot through its web interface. You can send messages and receive responses based on the configured dialog management.

### Using the Admin Interface
You can access the Django admin interface to manage user tokens and oversee bot activity. Log in with the superuser credentials you set up during the installation process. Here, you can manage bot settings and monitor user interactions.

### Sending Requests to the API
The project allows for interaction through its RESTful API. For example, you can send a POST request to the `/api/dialog/` endpoint to initiate a dialog with the bot:
```bash
curl -X POST https://your-server-domain/api/dialog/ -H "Content-Type: application/json" -d '{"message": "Hello, Bot!"}'
```
The bot will respond with a generated reply based on the dialog processing capabilities.

### Using the GPU Service
To utilize the GPU service for machine learning model processing, ensure the service is running. The service supports various AI models for tasks such as generating embeddings, document processing, and dialog responses.

### Using RAG Capabilities
The Django Assistant Bot includes robust RAG (Retrieval-Augmented Generation) functionality for knowledge-based question answering:

1. **Document Management**: Upload and process documents through the admin interface or API. The system supports various document formats and automatically processes them for effective information retrieval.

2. **Knowledge Base Creation**: Create and manage knowledge bases by associating relevant documents. These knowledge bases can be used to provide domain-specific context for AI responses.

3. **Improved Query Responses**: When querying the bot, the RAG system retrieves relevant information from indexed documents and incorporates this information into the response generation process, ensuring accurate and context-aware answers.

4. **API Access**: Access RAG functionality programmatically through dedicated API endpoints:
   ```bash
   # Example of querying with RAG
   curl -X POST https://your-server-domain/api/rag/query/ -H "Content-Type: application/json" -d '{"query": "What are the system requirements?", "knowledge_base_id": 1}'
   ```

By following these examples, you can effectively utilize the Django Assistant Bot to create and manage sophisticated bot functionalities.

## Configuration

To effectively configure the Django Assistant Bot project, several settings and environment variables must be defined. This section details the essential configurations needed for optimal operation.

### Environment Variables
Create a `.env` file in the root directory of the project to manage environment-specific variables securely. Below are key variables to include (based on `.env.example`):

- **DEBUG**: Set to `1` during development and `0` in production:
  ```plaintext
  DEBUG=1
  ```

- **SECRET_KEY**: A unique key for cryptographic signing:
  ```plaintext
  SECRET_KEY=your_secret_key_here
  ```

- **DATABASE_URL**: Connection string for your PostgreSQL database:
  ```plaintext
  DATABASE_URL=postgres://username:password@database_host:5432/dbname
  ```

- **CELERY_BROKER_URL**: URL for the message broker (Redis):
  ```plaintext
  CELERY_BROKER_URL=redis://redis_host:6379/0
  ```

- **ALLOWED_HOSTS**: A list of strings representing the host/domain names the Django site can serve:
  ```plaintext
  ALLOWED_HOSTS='your-domain.com,other-domain.com'
  ```

- **AI Model Configuration**: Various settings for different AI models:
  ```plaintext
  DEFAULT_AI_MODEL=llama3.1:8b
  EMBEDDING_AI_MODEL=ruBert
  DIALOG_FAST_AI_MODEL=llama3.1:8b
  DIALOG_STRONG_AI_MODEL=llama3.1:8b
  ```

- **External Services**: Configuration for Ollama and GPU service:
  ```plaintext
  OLLAMA_ENDPOINT=https://your-ollama-service
  GPU_SERVICE_ENDPOINT=https://your-gpu-service
  ```

### Project Configuration
The `example` directory contains configuration files that demonstrate how to set up a project using the Django Assistant Bot framework:

- **manage.py**: The Django management script for running commands.
- **example/**: Contains Django project settings and configurations.
- **bot/**: Contains example bot implementation and settings.

### GPU Service Configuration
The `gpu_service` directory contains the FastAPI service for AI model processing:

- **main.py**: The main FastAPI application.
- **models.py**: Definitions for AI models.
- **gunicorn_conf.py**: Configuration for the Gunicorn server when deploying the service.

By properly configuring these settings, you will enable the Django Assistant Bot to operate effectively and securely in your environment.

## Team & Contributors

The Django Assistant Bot project is made possible by the collaborative efforts of the following team members and contributors:

### Core Team
- **Project Lead**: Aleksandr Fedotov - [GitHub Profile](https://github.com/afedotov89)  
