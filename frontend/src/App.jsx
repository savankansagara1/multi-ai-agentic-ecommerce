import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Activity, ArrowDownLeft, ArrowRight, ArrowUpRight, BadgeCheck, Box, Check, ChevronDown, CircleHelp, Clock3, Command, Headphones, Laptop, Leaf, LoaderCircle, Menu, MessageCircle, Minus, PackageCheck, Plus, RefreshCw, Send, ShieldCheck, ShoppingBag, Sparkles, Trash2, Truck, X } from 'lucide-react'

const userId = 1
const money = value => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(value || 0))
const prompts = ['Find me a laptop for work', 'Show my cart', 'Track my latest order', 'What is your return policy?']

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, { headers: { 'Content-Type': 'application/json', ...options.headers }, ...options })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail || 'Something went wrong. Please try again.')
  return body
}

function IconButton({ children, label, onClick, className = '' }) { return <button className={`icon-button ${className}`} aria-label={label} title={label} onClick={onClick}>{children}</button> }

function App() {
  const [tab, setTab] = useState('cart')
  const [mobilePanel, setMobilePanel] = useState(false)
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'Hi there! I’m Forma, your personal shopping companion. Tell me what you’re looking for, or ask me about an order, your cart, or store policies.', time: 'Just now' }])
  const [input, setInput] = useState('')
  const [threadId] = useState(() => `forma_${Math.random().toString(36).slice(2, 10)}`)
  const [busy, setBusy] = useState(false)
  const [awaiting, setAwaiting] = useState(false)
  const [cart, setCart] = useState(null)
  const [orders, setOrders] = useState([])
  const [products, setProducts] = useState([])
  const [faqs, setFaqs] = useState([])
  const [toast, setToast] = useState('')
  const [query, setQuery] = useState('')
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  const refresh = async () => {
    const results = await Promise.allSettled([api(`/cart/?user_id=${userId}`), api(`/orders/?user_id=${userId}`), api('/products/?limit=50'), api('/support/faqs')])
    if (results[0].status === 'fulfilled') setCart(results[0].value)
    if (results[1].status === 'fulfilled') setOrders(results[1].value)
    if (results[2].status === 'fulfilled') setProducts(results[2].value)
    if (results[3].status === 'fulfilled') setFaqs(results[3].value)
  }
  useEffect(() => { refresh() }, [])
  useEffect(() => { if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight }, [messages, busy])
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 3200); return () => clearTimeout(timer) }, [toast])

  const send = async (raw = input) => {
    const text = raw.trim()
    if (!text || busy) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text, time: 'Now' }])
    setBusy(true)
    try {
      const data = await api('/chat/', { method: 'POST', body: JSON.stringify({ message: text, user_id: userId, thread_id: threadId }) })
      setMessages(prev => [...prev, { role: 'assistant', content: data.response, intent: data.intent, time: new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) }])
      setAwaiting(data.awaiting_confirmation)
      await refresh()
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: `I couldn't reach the shopping assistant. ${error.message}`, time: 'Now', error: true }])
    } finally { setBusy(false); inputRef.current?.focus() }
  }

  const changeQty = async (variant, quantity) => {
    try {
      await api(`/cart/items/${variant}`, { method: 'PUT', body: JSON.stringify({ quantity, user_id: userId }) }); await refresh()
    } catch (error) { setToast(error.message) }
  }
  const addProduct = async variant => {
    try { await api('/cart/items', { method: 'POST', body: JSON.stringify({ variant_id: variant.id, quantity: 1, user_id: userId }) }); await refresh(); setToast('Added to your cart') }
    catch (error) { setToast(error.message) }
  }

  const filteredProducts = products.filter(product => `${product.name} ${product.brand || ''} ${product.description || ''}`.toLowerCase().includes(query.toLowerCase()))
  const tabs = [{ id: 'cart', label: 'Your bag', icon: ShoppingBag, count: cart?.item_count || 0 }, { id: 'orders', label: 'Orders', icon: PackageCheck }, { id: 'catalog', label: 'Discover', icon: Laptop }, { id: 'support', label: 'Help center', icon: CircleHelp }]

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-mark"><span>f</span><i /></div><div><strong>forma<span>.</span></strong><small>Thoughtful shopping, made personal</small></div></div>
      <div className="topbar-center"><span className="status-dot" /> Your shopping assistant is ready</div>
      <div className="top-actions"><a className="docs-link" href="/docs" target="_blank" rel="noreferrer">Developer docs <ArrowUpRight size={14}/></a><span className="avatar">S</span><span className="user-name">Sam</span><IconButton label="Refresh your shopping data" onClick={refresh}><RefreshCw size={16}/></IconButton><button className="mobile-menu" onClick={() => setMobilePanel(!mobilePanel)}><Menu size={20}/></button></div>
    </header>
    <main className="workspace">
      <section className="conversation">
        <div className="conversation-head"><div><div className="eyebrow"><Sparkles size={13}/> YOUR PERSONAL SHOPPING SPACE</div><h1>Good afternoon, Sam<span>.</span></h1><p>What can I help you find today?</p></div><div className="session-chip"><span className="live-pulse"/> AI concierge <ChevronDown size={14}/></div></div>
        <div className="chat-area" ref={scrollRef}>
          <div className="day-divider"><span/> TODAY <span/></div>
          {messages.map((message, index) => <article className={`message-row ${message.role} ${message.error ? 'message-error' : ''}`} key={index}>
            {message.role === 'assistant' && <div className="assistant-avatar"><Sparkles size={17}/></div>}
            <div className="message-content"><div className="message-meta">{message.role === 'assistant' ? 'FORMA ASSISTANT' : 'YOU'} <span>· {message.time}</span>{message.intent && <em>{message.intent.replaceAll('_', ' ')}</em>}</div><div className="bubble">{message.role === 'assistant' ? <ReactMarkdown>{message.content}</ReactMarkdown> : message.content}</div></div>
            {message.role === 'user' && <div className="user-avatar">S</div>}
          </article>)}
          {busy && <div className="message-row assistant"><div className="assistant-avatar"><Sparkles size={17}/></div><div className="message-content"><div className="message-meta">FORMA ASSISTANT <span>· thinking</span></div><div className="bubble thinking"><i/><i/><i/></div></div></div>}
        </div>
        <div className="composer-wrap">
          {awaiting && <div className="confirm-card"><div className="confirm-icon"><ShieldCheck size={18}/></div><div><strong>One last check</strong><span>This action needs your confirmation.</span></div><button onClick={() => { setAwaiting(false); send('yes') }}>Confirm <Check size={14}/></button><button className="cancel-confirm" onClick={() => { setAwaiting(false); send('no') }}>Cancel</button></div>}
          <div className="prompt-row"><span>TRY ASKING</span>{prompts.map(prompt => <button key={prompt} onClick={() => send(prompt)}>{prompt}<ArrowUpRight size={12}/></button>)}</div>
          <form className="composer" onSubmit={event => { event.preventDefault(); send() }}><button type="button" className="composer-add" title="Browse catalog" onClick={() => setTab('catalog')}><Plus size={19}/></button><input ref={inputRef} value={input} onChange={event => setInput(event.target.value)} placeholder="Ask anything about shopping…" disabled={busy}/><span className="shortcut"><Command size={12}/> K</span><button type="submit" className="send-button" disabled={busy || !input.trim()}>{busy ? <LoaderCircle className="spin" size={18}/> : <Send size={17}/>}</button></form>
          <div className="composer-note"><ShieldCheck size={12}/> Your personal details and orders stay private <span>·</span> AI can make mistakes</div>
        </div>
      </section>

      <aside className={`side-panel ${mobilePanel ? 'mobile-open' : ''}`}>
        <div className="side-heading"><div><div className="eyebrow">YOUR ACCOUNT</div><h2>At a glance</h2></div><IconButton label="Close panel" className="close-panel" onClick={() => setMobilePanel(false)}><X size={17}/></IconButton><span className="sync-label"><span className="status-dot"/> LIVE</span></div>
        <div className="stat-strip"><div><span>IN YOUR BAG</span><strong>{cart?.item_count ?? '—'} <small>items</small></strong></div><div><span>RECENT ORDERS</span><strong>{orders.length} <small>orders</small></strong></div><div className="stat-icon"><ShoppingBag size={18}/></div></div>
        <div className="panel-tabs">{tabs.map(({ id, label, icon: Icon, count }) => <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}><Icon size={15}/><span>{label}</span>{count > 0 && <b>{count}</b>}</button>)}</div>
        <section className="panel-content" key={tab}>
          {tab === 'cart' && <><div className="section-title"><div><h3>Your bag <span>({cart?.item_count || 0})</span></h3><p>A little something for you.</p></div><IconButton label="Refresh cart" onClick={refresh}><RefreshCw size={15}/></IconButton></div>
            {cart?.items?.length ? <div className="cart-list">{cart.items.map(item => <div className="cart-item" key={item.product_variant_id}><div className="product-art"><Laptop size={25}/><span>F</span></div><div className="cart-info"><strong>{item.product_name}</strong><span>{item.variant_name} · {item.sku}</span><b>{money(item.unit_price)}</b><div className="quantity"><button onClick={() => changeQty(item.product_variant_id, item.quantity - 1)}><Minus size={12}/></button><span>{item.quantity}</span><button onClick={() => changeQty(item.product_variant_id, item.quantity + 1)}><Plus size={12}/></button></div></div><IconButton label="Remove item" className="remove-item" onClick={() => changeQty(item.product_variant_id, 0)}><Trash2 size={15}/></IconButton></div>)}</div> : <Empty icon={ShoppingBag} title="Your bag is taking a breather" detail="Ask Forma to find something you’ll love." action="Explore the catalog" onClick={() => setTab('catalog')}/>}
            <div className="cart-total"><div><span>Subtotal</span><strong>{money(cart?.total)}</strong></div><div><span>Shipping</span><strong className="free">Complimentary</strong></div><div className="total-line"><span>Total</span><strong>{money(cart?.total)}</strong></div><button className="checkout" disabled={!cart?.items?.length} onClick={() => send('Place order for my cart')}>Continue to checkout <ArrowRight size={16}/></button><div className="secure-note"><ShieldCheck size={13}/> Secure checkout · Easy returns</div></div>
          </>}
          {tab === 'orders' && <><div className="section-title"><div><h3>Your orders</h3><p>Everything you’ve ordered, in one place.</p></div><IconButton label="Refresh orders" onClick={refresh}><RefreshCw size={15}/></IconButton></div>{orders.length ? <div className="orders-list">{orders.map(order => <div className="order-card" key={order.order_id}><div className="order-top"><div className="order-icon"><Box size={17}/></div><div><span>ORDER {order.order_number}</span><small>{new Date(order.created_at).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}</small></div><Status status={order.status}/></div><p>{order.items_summary || `${order.item_count} items`}</p><div className="order-bottom"><strong>{money(order.total_amount)}</strong><button onClick={() => send(`Track order ${order.order_number}`)}>Track order <ArrowRight size={13}/></button></div></div>)}</div> : <Empty icon={PackageCheck} title="No orders just yet" detail="Your next favorite thing is out there." action="Discover products" onClick={() => setTab('catalog')}/>}</>}
          {tab === 'catalog' && <><div className="section-title"><div><h3>Find your next favorite</h3><p>Thoughtful picks, selected for you.</p></div><span className="count-pill">{filteredProducts.length} ITEMS</span></div><label className="search-box"><Laptop size={16}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search products or brands"/><span>⌘ F</span></label>{filteredProducts.length ? <div className="catalog-list">{filteredProducts.map(product => <div className="catalog-card" key={product.id}><div className="catalog-visual"><span className="catalog-brand">{product.brand || 'FORMA EDIT'}</span><div className="catalog-device"><Laptop size={42}/></div><span className="rating">★ {product.rating || '4.8'}</span></div><div className="catalog-detail"><div className="catalog-name"><div><h4>{product.name}</h4><span>{product.brand || 'Curated for you'}</span></div><BadgeCheck size={16}/></div><p>{product.description}</p>{(product.variants || []).slice(0, 3).map(variant => <div className="variant-row" key={variant.id}><div><span>{variant.name}</span><b>{money(variant.price)}</b></div><button onClick={() => addProduct(variant)} aria-label={`Add ${variant.name} to bag`}><Plus size={15}/></button></div>)}</div></div>)}</div> : <Empty icon={Laptop} title="Nothing matched that search" detail="Try a different name or brand."/>}</>}
          {tab === 'support' && <><div className="section-title"><div><h3>Here when you need us</h3><p>Honest answers, helpful humans.</p></div></div><div className="support-banner"><div className="support-icon"><Headphones size={19}/></div><div><strong>A real person, if you need one</strong><p>Our care team is ready to help with the tricky things.</p></div><button onClick={() => { const issue = window.prompt('Briefly describe the issue you need help with:'); if (issue?.trim()) send(`I want to escalate this issue to a human support agent: ${issue}`) }}><ArrowUpRight size={15}/></button></div><div className="policy-heading"><div><ShieldCheck size={15}/><strong>Store policies</strong></div><span>GROUNDED ANSWERS</span></div>{faqs.length ? <div className="faq-list">{faqs.map((faq, index) => <details key={faq.id || index}><summary>{faq.title}<ChevronDown size={15}/></summary><p>{faq.content}</p></details>)}</div> : <div className="loading-state"><LoaderCircle className="spin" size={18}/> Loading help articles</div>}<button className="ask-policy" onClick={() => { setInput('What is your return policy?'); inputRef.current?.focus() }}>Ask Forma about a policy <ArrowRight size={14}/></button></>}
        </section>
        <div className="panel-footer"><div className="secure-badge"><div><Leaf size={14}/></div><span>Built with care, powered by AI</span></div><a href="/health" target="_blank" rel="noreferrer">System status <ArrowUpRight size={12}/></a></div>
      </aside>
    </main>
    {toast && <div className="toast"><Check size={16}/>{toast}<button onClick={() => setToast('')}><X size={14}/></button></div>}
  </div>
}

function Status({ status }) { return <span className={`status-badge ${String(status).toLowerCase()}`}>{status}</span> }
function Empty({ icon: Icon, title, detail, action, onClick }) { return <div className="empty-state"><div className="empty-icon"><Icon size={23}/></div><strong>{title}</strong><p>{detail}</p>{action && <button onClick={onClick}>{action} <ArrowRight size={13}/></button>}</div> }

export default App
