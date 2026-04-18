/**
 * 页码导航组件
 * 提供页码跳转、上一页/下一页、快捷键支持
 */

import { useEffect } from 'react';
import { Button, InputNumber, Space } from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import './styles.css';

interface PageNavigationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const PageNavigation = ({
  currentPage,
  totalPages,
  onPageChange,
}: PageNavigationProps) => {
  /**
   * 上一页
   */
  const handlePrevPage = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  /**
   * 下一页
   */
  const handleNextPage = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  /**
   * 跳转到指定页
   */
  const handlePageInput = (value: number | null) => {
    if (value && value >= 1 && value <= totalPages) {
      onPageChange(value);
    }
  };

  /**
   * 快捷键支持（←/→）
   */
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // 如果焦点在输入框中，不处理快捷键
      if (
        document.activeElement?.tagName === 'INPUT' ||
        document.activeElement?.tagName === 'TEXTAREA'
      ) {
        return;
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        handlePrevPage();
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        handleNextPage();
      }
    };

    window.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [currentPage, totalPages]);

  /**
   * 生成页码按钮
   */
  const renderPageButtons = () => {
    const buttons = [];
    const maxButtons = 7; // 最多显示7个页码按钮

    if (totalPages <= maxButtons) {
      // 总页数少于最大按钮数，显示所有页码
      for (let i = 1; i <= totalPages; i++) {
        buttons.push(
          <Button
            key={i}
            type={i === currentPage ? 'primary' : 'default'}
            onClick={() => onPageChange(i)}
          >
            {i}
          </Button>
        );
      }
    } else {
      // 总页数多于最大按钮数，显示部分页码
      buttons.push(
        <Button
          key={1}
          type={1 === currentPage ? 'primary' : 'default'}
          onClick={() => onPageChange(1)}
        >
          1
        </Button>
      );

      if (currentPage > 3) {
        buttons.push(<span key="ellipsis-start">...</span>);
      }

      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);

      for (let i = start; i <= end; i++) {
        buttons.push(
          <Button
            key={i}
            type={i === currentPage ? 'primary' : 'default'}
            onClick={() => onPageChange(i)}
          >
            {i}
          </Button>
        );
      }

      if (currentPage < totalPages - 2) {
        buttons.push(<span key="ellipsis-end">...</span>);
      }

      buttons.push(
        <Button
          key={totalPages}
          type={totalPages === currentPage ? 'primary' : 'default'}
          onClick={() => onPageChange(totalPages)}
        >
          {totalPages}
        </Button>
      );
    }

    return buttons;
  };

  return (
    <div className="page-navigation">
      <Space size="middle">
        {/* 上一页按钮 */}
        <Button
          icon={<LeftOutlined />}
          onClick={handlePrevPage}
          disabled={currentPage === 1}
        >
          上一页
        </Button>

        {/* 页码按钮 */}
        <Space size="small">{renderPageButtons()}</Space>

        {/* 下一页按钮 */}
        <Button
          icon={<RightOutlined />}
          onClick={handleNextPage}
          disabled={currentPage === totalPages}
        >
          下一页
        </Button>

        {/* 页码输入跳转 */}
        <Space size="small">
          <span>跳转到</span>
          <InputNumber
            min={1}
            max={totalPages}
            value={currentPage}
            onChange={handlePageInput}
            style={{ width: 60 }}
          />
          <span>页</span>
        </Space>

        {/* 页码信息 */}
        <span className="page-info">
          第 {currentPage} 页 / 共 {totalPages} 页
        </span>
      </Space>
    </div>
  );
};

export default PageNavigation;
