/**
 * 同步滚动Hook
 * 实现左右PDF的同步滚动和缩放
 */

import { useEffect, useRef, useState } from 'react';

interface UseSyncScrollOptions {
  enabled?: boolean; // 是否启用同步滚动
}

export const useSyncScroll = (options: UseSyncScrollOptions = {}) => {
  const { enabled = true } = options;

  // 左侧和右侧容器的ref
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);

  // 缩放比例
  const [scale, setScale] = useState(1);

  // 当前正在滚动的容器（防止循环触发）
  const scrollingRef = useRef<'left' | 'right' | null>(null);

  /**
   * 同步滚动处理
   */
  const handleScroll = (source: 'left' | 'right') => {
    if (!enabled) return;

    return (event: Event) => {
      const target = event.target as HTMLDivElement;

      // 如果当前正在同步滚动，跳过
      if (scrollingRef.current && scrollingRef.current !== source) {
        return;
      }

      // 标记当前滚动源
      scrollingRef.current = source;

      // 计算滚动比例
      const scrollTop = target.scrollTop;
      const scrollHeight = target.scrollHeight;
      const clientHeight = target.clientHeight;
      const scrollRatio = scrollTop / (scrollHeight - clientHeight);

      // 同步到另一侧
      const otherRef = source === 'left' ? rightRef : leftRef;
      if (otherRef.current) {
        const otherScrollHeight = otherRef.current.scrollHeight;
        const otherClientHeight = otherRef.current.clientHeight;
        const otherScrollTop = scrollRatio * (otherScrollHeight - otherClientHeight);

        otherRef.current.scrollTop = otherScrollTop;
      }

      // 延迟重置滚动源标记
      setTimeout(() => {
        scrollingRef.current = null;
      }, 50);
    };
  };

  /**
   * 绑定滚动事件
   */
  useEffect(() => {
    if (!enabled) return;

    const leftElement = leftRef.current;
    const rightElement = rightRef.current;

    if (!leftElement || !rightElement) return;

    const leftScrollHandler = handleScroll('left');
    const rightScrollHandler = handleScroll('right');

    if (leftScrollHandler && rightScrollHandler) {
      leftElement.addEventListener('scroll', leftScrollHandler);
      rightElement.addEventListener('scroll', rightScrollHandler);

      return () => {
        leftElement.removeEventListener('scroll', leftScrollHandler);
        rightElement.removeEventListener('scroll', rightScrollHandler);
      };
    }
  }, [enabled]);

  /**
   * 缩放控制
   */
  const zoomIn = () => {
    setScale((prev) => Math.min(prev + 0.1, 2)); // 最大200%
  };

  const zoomOut = () => {
    setScale((prev) => Math.max(prev - 0.1, 0.5)); // 最小50%
  };

  const resetZoom = () => {
    setScale(1);
  };

  const setZoom = (newScale: number) => {
    setScale(Math.max(0.5, Math.min(2, newScale)));
  };

  /**
   * 滚动到指定位置
   */
  const scrollTo = (scrollTop: number) => {
    if (leftRef.current) {
      leftRef.current.scrollTop = scrollTop;
    }
    if (rightRef.current) {
      rightRef.current.scrollTop = scrollTop;
    }
  };

  /**
   * 滚动到顶部
   */
  const scrollToTop = () => {
    scrollTo(0);
  };

  return {
    leftRef,
    rightRef,
    scale,
    zoomIn,
    zoomOut,
    resetZoom,
    setZoom,
    scrollTo,
    scrollToTop,
  };
};
