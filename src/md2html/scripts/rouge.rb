require 'json'
require 'rouge'
STDOUT.sync = true
puts JSON.generate(ready: true)
STDIN.each_line do |line|
  begin
    request = JSON.parse(line)
    if request['code']
      lexer = Rouge::Lexer.find(request['language']) || Rouge::Lexers::PlainText
      result = Rouge::Formatters::HTML.new.format(lexer.lex(request['code']))
    else
      theme = Rouge::Theme.find(request['style'])
      unless theme
        raise ArgumentError, "Unknown Rouge theme #{request['style'].inspect} (Rouge #{Rouge.version}). " \
          "Choose another theme or update with 'gem install --user-install rouge'."
      end
      result = theme.new(scope: '.codehilite').render
    end
    puts JSON.generate(value: result)
  rescue => error
    puts JSON.generate(error: error.message)
  end
end
