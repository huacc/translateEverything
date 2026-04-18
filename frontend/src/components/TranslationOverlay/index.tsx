import './index.css'

interface TranslationBlock {
  id: string
  pageNum: number
  status: 'pending' | 'translating' | 'completed'
  content?: string
  position?: {
    x: number
    y: number
    width: number
    height: number
  }
}

interface TranslationOverlayProps {
  blocks: TranslationBlock[]
  currentPage: number
}

const TranslationOverlay = ({
  blocks,
  currentPage,
}: TranslationOverlayProps) => {
  const currentPageBlocks = blocks.filter(block => block.pageNum === currentPage)
  const positionedBlocks = currentPageBlocks.filter(block => block.position)
  const floatingBlocks = currentPageBlocks.filter(block => !block.position)

  return (
    <div className="translation-overlay">
      {positionedBlocks.map(block => (
        <div
          key={block.id}
          className={`translation-block translation-block-${block.status}`}
          style={
            block.position
              ? {
                  left: `${block.position.x}px`,
                  top: `${block.position.y}px`,
                  width: `${block.position.width}px`,
                  height: `${block.position.height}px`,
                }
              : undefined
          }
        >
          {block.status === 'translating' && (
            <div className="translation-block-indicator">
              <span className="translation-block-spinner" />
            </div>
          )}
          {block.content && (
            <div className="translation-block-content">{block.content}</div>
          )}
        </div>
      ))}

      {floatingBlocks.length > 0 && (
        <div className="translation-overlay-list">
          {floatingBlocks.slice(-3).map(block => (
            <div
              key={block.id}
              className={`translation-overlay-card translation-overlay-card-${block.status}`}
            >
              <div className="translation-overlay-card-header">
                <span>{block.id}</span>
                <span>{block.status === 'completed' ? '已完成' : '处理中'}</span>
              </div>
              {block.content && (
                <div className="translation-overlay-card-content">
                  {block.content}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default TranslationOverlay
