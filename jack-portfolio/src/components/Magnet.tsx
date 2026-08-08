import { type ReactNode, useRef, useState } from 'react';
import { motion } from 'framer-motion';

interface MagnetProps {
  children: ReactNode;
  padding?: number;
  strength?: number;
  className?: string;
}

export default function Magnet({
  children,
  padding = 150,
  strength = 3,
  className = '',
}: MagnetProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isActive, setIsActive] = useState(false);

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;

    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    const distX = e.clientX - centerX;
    const distY = e.clientY - centerY;
    const dist = Math.sqrt(distX * distX + distY * distY);

    if (dist < padding) {
      setIsActive(true);
      setPosition({ x: distX / strength, y: distY / strength });
    } else {
      setIsActive(false);
      setPosition({ x: 0, y: 0 });
    }
  };

  return (
    <motion.div
      ref={ref}
      className={className}
      onMouseMove={handleMouseMove}
      onMouseLeave={() => {
        setIsActive(false);
        setPosition({ x: 0, y: 0 });
      }}
      animate={{ x: position.x, y: position.y }}
      transition={{
        type: 'tween',
        duration: isActive ? 0.3 : 0.6,
        ease: isActive ? 'easeOut' : 'easeInOut',
      }}
      style={{ willChange: 'transform' }}
    >
      {children}
    </motion.div>
  );
}
