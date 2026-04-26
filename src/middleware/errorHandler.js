function notFoundHandler(req, res, next) {
  const error = new Error(`Route not found: ${req.method} ${req.originalUrl}`);
  error.statusCode = 404;
  next(error);
}

function errorHandler(error, req, res, _next) {
  const statusCode = error.statusCode || 500;
  const response = {
    error: statusCode >= 500 ? 'Internal server error' : error.message,
  };

  if (process.env.NODE_ENV !== 'production') {
    response.detail = error.message;
  }

  console.error(error);
  res.status(statusCode).json(response);
}

module.exports = { errorHandler, notFoundHandler };
