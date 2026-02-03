# Chatow - AI SaaS with Smart Model Routing

A ChatGPT Pro clone with intelligent model routing and credit-based billing.

## Features

- **Smart Model Routing**: Automatically routes messages to the optimal model
  - Simple queries → GPT-4o-mini (1 credit)
  - Complex queries → GPT-4o (20 credits)
- **Credit System**: Pay-as-you-go billing with real-time balance updates
- **Streaming Responses**: Real-time typewriter effect for responses
- **Modern UI**: Beautiful dark theme with gradient accents
- **Markdown Support**: Code highlighting, tables, and math rendering

## Tech Stack

### Frontend
- Next.js 14 (App Router)
- Tailwind CSS
- Shadcn/UI components
- Framer Motion for animations
- Supabase Client for auth and real-time

### Backend
- Python FastAPI
- OpenAI API for LLM
- Supabase Python client
- Server-Sent Events for streaming

### Infrastructure
- Supabase (Auth, PostgreSQL, Realtime)
- Lemon Squeezy (Payments)

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- Supabase account
- OpenAI API key

### 1. Setup Supabase

1. Create a new Supabase project
2. Run the SQL migration in the Supabase SQL Editor:

```sql
-- See supabase/schema.sql for full migration
```

3. Create test user via Authentication > Users > Add User:
   - Email: `admin@test.com`
   - Password: `test123456`

4. Add credits to test user:
```sql
UPDATE public.profiles
SET credit_balance = 1000000, is_test_user = true
WHERE email = 'admin@test.com';
```

### 2. Setup Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your credentials
# Then run:
uvicorn app.main:app --reload --port 8000
```

### 3. Setup Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.local.example .env.local

# Edit .env.local with your Supabase credentials
# Then run:
npm run dev
```

### 4. Access the App

Open http://localhost:3000 and login with:
- Email: `admin@test.com`
- Password: `test123456`

## Project Structure

```
chatow/
├── frontend/                 # Next.js frontend
│   ├── src/
│   │   ├── app/             # App router pages
│   │   ├── components/      # React components
│   │   ├── lib/             # Utilities & Supabase client
│   │   └── types/           # TypeScript types
│   └── package.json
│
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── routers/         # API endpoints
│   │   ├── services/        # Business logic
│   │   ├── config.py        # Settings
│   │   └── main.py          # App entry
│   └── requirements.txt
│
├── supabase/                 # Database migrations
│   └── schema.sql
│
└── README.md
```

## API Endpoints

### Chat
- `POST /api/chat` - Send message (streaming response)
- `GET /api/chat/history/{session_id}` - Get chat history

### User
- `GET /api/user/balance` - Get credit balance
- `GET /api/user/me` - Get user info

### Webhooks
- `POST /api/webhooks/lemon-squeezy` - Handle payment webhooks

## Model Routing Logic

The Smart Router analyzes each message using GPT-4o-mini to classify intent:

| Classification | Examples | Model Used | Cost |
|---------------|----------|------------|------|
| SIMPLE | Greetings, basic facts, translations | GPT-4o-mini | 1 credit |
| COMPLEX | Coding, math, reasoning, creative writing | GPT-4o | 20 credits |

Users can also manually select:
- **Auto** - Smart routing (default)
- **Fast** - Always use GPT-4o-mini
- **Pro** - Always use GPT-4o

## Environment Variables

### Frontend (.env.local)
```
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

### Backend (.env)
```
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret
OPENAI_API_KEY=your-openai-key
```

## Deployment to Vercel

### Backend Deployment

1. **Install Vercel CLI** (if not already installed):
   ```bash
   npm i -g vercel
   ```

2. **Navigate to backend directory**:
   ```bash
   cd backend
   ```

3. **Deploy to Vercel**:
   ```bash
   vercel
   ```
   - Follow the prompts to link/create a project
   - When asked about settings, accept defaults

4. **Set Environment Variables** in Vercel Dashboard:
   - Go to your project → Settings → Environment Variables
   - Add all variables from `backend/.env`:
     - `SUPABASE_URL`
     - `SUPABASE_SERVICE_KEY`
     - `SUPABASE_JWT_SECRET`
     - `OPENAI_API_KEY`
     - `ALLOWED_ORIGINS` (comma-separated list of frontend URLs, e.g., `https://your-frontend.vercel.app,https://your-custom-domain.com`)
     - `DEBUG=false` (for production)
     - Optional: `SIMPLE_MODEL`, `COMPLEX_MODEL`, `SIMPLE_MODEL_COST`, `COMPLEX_MODEL_COST`
     - Optional: `LEMON_SQUEEZY_WEBHOOK_SECRET`

4. **Redeploy** after adding environment variables:
   ```bash
   vercel --prod
   ```

5. **Note your backend URL** (e.g., `https://your-backend.vercel.app`)

### Frontend Deployment

1. **Navigate to frontend directory**:
   ```bash
   cd frontend
   ```

2. **Deploy to Vercel**:
   ```bash
   vercel
   ```
   - Follow the prompts to link/create a project
   - When asked about settings, accept defaults

3. **Set Environment Variables** in Vercel Dashboard:
   - Go to your project → Settings → Environment Variables
   - Add all variables from `frontend/.env.local`:
     - `NEXT_PUBLIC_SUPABASE_URL`
     - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
     - `NEXT_PUBLIC_API_URL` (your backend Vercel URL, e.g., `https://your-backend.vercel.app`)
     - `NEXT_PUBLIC_LEMON_SQUEEZY_STORE_URL`
     - `NEXT_PUBLIC_LEMON_SQUEEZY_STARTER_VARIANT_ID`
     - `NEXT_PUBLIC_LEMON_SQUEEZY_PRO_VARIANT_ID`
     - `NEXT_PUBLIC_LEMON_SQUEEZY_UNLIMITED_VARIANT_ID`

4. **Update Backend CORS**:
   - Go to your backend Vercel project → Settings → Environment Variables
   - Update `ALLOWED_ORIGINS` to include your frontend URL:
     ```
     https://your-frontend.vercel.app,https://your-custom-domain.com
     ```

5. **Redeploy both projects**:
   ```bash
   # In frontend directory
   vercel --prod
   
   # In backend directory
   vercel --prod
   ```

### Post-Deployment Checklist

- [ ] Backend health check: Visit `https://your-backend.vercel.app/health`
- [ ] Frontend loads correctly
- [ ] User can login
- [ ] Chat messages are sent and received
- [ ] Credits are deducted correctly
- [ ] Webhooks are configured (if using Lemon Squeezy)

### Troubleshooting

**Backend returns 500 errors:**
- Check Vercel function logs: Project → Functions → View Logs
- Verify all environment variables are set correctly
- Check that `mangum` is in `requirements.txt`

**CORS errors:**
- Verify `ALLOWED_ORIGINS` includes your frontend URL
- Ensure no trailing slashes in URLs
- Redeploy backend after updating CORS settings

**Frontend can't connect to backend:**
- Verify `NEXT_PUBLIC_API_URL` is set correctly
- Check browser console for exact error
- Ensure backend is deployed and accessible

## License

MIT
# vion1
