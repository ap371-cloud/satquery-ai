import { motion as m, AnimatePresence } from 'motion/react'

export { AnimatePresence }

export const motion = m

export const spring = { type: 'spring', stiffness: 520, damping: 34 }
export const gentle = [0.2, 0.8, 0.25, 1]

export function Fade({ children, delay = 0, className = '', ...rest }) {
  return (
    <m.div className={className} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      transition={{ duration: 0.4, delay, ease: gentle }} {...rest}>
      {children}
    </m.div>
  )
}

export function Reveal({ children, delay = 0, y = 18, className = '', ...rest }) {
  return (
    <m.div className={className} initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.35, delay, ease: gentle }} {...rest}>
      {children}
    </m.div>
  )
}

export const itemVariants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.32, ease: gentle } },
}

export function Stagger({ children, className = '', gap = 0.055, ...rest }) {
  return (
    <m.div className={className} initial="hidden" animate="show" {...rest}
      variants={{ hidden: {}, show: { transition: { staggerChildren: gap } } }}>
      {children}
    </m.div>
  )
}

export function StaggerItem({ children, className = '', ...rest }) {
  return (
    <m.div className={className} variants={itemVariants} {...rest}>
      {children}
    </m.div>
  )
}

export function Appear({ show, children, className = '', ...rest }) {
  return (
    <AnimatePresence initial={false} mode="wait">
      {show ? (
        <m.div className={className} key="appear" initial={{ opacity: 0, y: 6, scale: 0.995 }}
          animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 4, scale: 0.995 }}
          transition={{ duration: 0.24, ease: gentle }} {...rest}>
          {children}
        </m.div>
      ) : null}
    </AnimatePresence>
  )
}

export function HeightOpen({ show, children, className = '', ...rest }) {
  return (
    <AnimatePresence initial={false}>
      {show ? (
        <m.div className={className} key="open" initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.3, ease: gentle }} style={{ overflow: 'hidden' }} {...rest}>
          {children}
        </m.div>
      ) : null}
    </AnimatePresence>
  )
}

export function MotionButton({ children, className = '', onClick, disabled, title, ...rest }) {
  return (
    <m.button
      className={className}
      onClick={onClick}
      disabled={disabled}
      title={title}
      whileHover={disabled ? undefined : { y: -1, scale: 1.01 }}
      whileTap={disabled ? undefined : { scale: 0.96 }}
      transition={spring}
      {...rest}
    >
      {children}
    </m.button>
  )
}

export function MotionCard({ children, className = '', ...rest }) {
  return (
    <m.div className={className} whileHover={{ y: -2, scale: 1.004 }}
      transition={spring} {...rest}>
      {children}
    </m.div>
  )
}

export function Pulse({ children, className = '', delay = 0, ...rest }) {
  return (
    <m.div className={className}
      animate={{ opacity: [1, 0.55, 1] }}
      transition={{ duration: 1.4, delay, repeat: Infinity, ease: 'easeInOut' }} {...rest}>
      {children}
    </m.div>
  )
}